"""
Chargement et nettoyage des données NFL Big Data Bowl (Python pur).

Sources (dépôt nfl-big-data-bowl-regional-event-data) :
  - players.csv           : 1 679 joueurs (université, poste, physique)
  - pffScoutingData.csv   : 188 254 lignes joueur x action (rôle, production)
  - plays.csv             : 8 557 actions de passe (contexte, résultat)
  - tracking/*.csv        : 8,3 M lignes de positionnement (voir nfl_tracking)

Le nettoyage reprend la logique du projet « universités » : normalisation des
noms d'établissements, exclusion des valeurs manquantes, filtrage des
établissements sous-représentés.
"""

from __future__ import annotations

import csv
import html
import os
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Groupes de postes, dérivés du rôle PFF dominant
# ---------------------------------------------------------------------------
# On n'utilise pas `officialPosition` seul : un OLB peut être pass rusher ou
# défenseur de couverture selon le schéma. Le rôle PFF réellement joué sur le
# terrain (majoritaire sur ses snaps) est un classement plus fidèle.

GROUPES = {
    "Pass Rush": "Pass rush",
    "Pass Block": "Protection",
    "Coverage": "Couverture",
    "Pass Route": "Réception",
    "Pass": "Quarterback",
}

# Ordre d'affichage dans les livrables.
ORDRE_GROUPES = ["Pass Rush", "Pass Block", "Coverage", "Pass Route", "Pass"]

# Sens de lecture de la métrique de production : True si « plus haut = mieux ».
SENS_PRODUCTION = {
    "Pass Rush": True,    # taux de pression générée
    "Pass Block": False,  # taux de pression concédée
    "Coverage": False,    # distance au receveur (serrer = mieux)
    "Pass Route": True,   # séparation obtenue
    "Pass": True,         # efficacité de passe
}

LIBELLE_PRODUCTION = {
    "Pass Rush": "Taux de pression générée",
    "Pass Block": "Taux de pression concédée",
    "Coverage": "Distance de couverture au lâcher",
    "Pass Route": "Séparation au lâcher",
    "Pass": "Efficacité de passe",
}

# ---------------------------------------------------------------------------
# Familles de postes : normalisation fine
# ---------------------------------------------------------------------------
# Les percentiles doivent être calculés sur des joueurs réellement
# comparables. Dans le groupe « Réception », un running back qui sort du
# backfield obtient mécaniquement 7 yards de séparation (personne ne le
# couvre) là où un wide receiver affronte un cornerback à 3 yards : les noter
# sur la même échelle reviendrait à conclure que les RB sont meilleurs
# receveurs que les WR. On normalise donc par famille fine, tout en agrégeant
# par groupe large pour conserver des effectifs suffisants par université.

FAMILLES_POSTES = {
    # Réception
    "WR": "WR",
    "TE": "TE",
    "RB": "RB",
    "FB": "RB",
    # Couverture
    "CB": "CB",
    "DB": "CB",
    "FS": "Safety",
    "SS": "Safety",
    "ILB": "Linebacker",
    "MLB": "Linebacker",
    "LB": "Linebacker",
    "OLB": "Edge",
    # Pass rush
    "DE": "DE",
    "DT": "DT",
    "NT": "DT",
    # Protection
    "T": "Tackle",
    "G": "Intérieur OL",
    "C": "Intérieur OL",
    # Quarterback
    "QB": "QB",
}

# En dessous de cet effectif, la famille fine est trop petite pour un
# percentile fiable : on retombe sur le groupe large.
MIN_EFFECTIF_FAMILLE = 10


def famille_normalisation(role: str, poste: str) -> str:
    """Clé de normalisation d'un joueur : (rôle, famille de postes)."""
    return f"{role}|{FAMILLES_POSTES.get(poste, poste)}"

# ---------------------------------------------------------------------------
# Normalisation des noms d'universités
# ---------------------------------------------------------------------------
# Attention : « Miami » (Floride) et « Miami, O. » (Miami of Ohio) sont deux
# établissements distincts ; de même « Ohio » et « Ohio State ». On ne fusionne
# que les cas sans ambiguïté.

ALIAS_UNIVERSITES = {
    "USC": "Southern California",
    "Alabama-Tuscaloosa, University": "Alabama",
    "Southern U.": "Southern",
}

UNIVERSITE_MANQUANTE = {"NA", "", "N/A", "None", "nan"}


def normaliser_universite(nom: str) -> str | None:
    """Nettoie un nom d'université. Retourne None si la valeur est manquante."""
    if nom is None:
        return None
    # Les CSV contiennent des entités HTML : « Texas A&amp;M » -> « Texas A&M ».
    nom = html.unescape(nom).strip()
    if nom in UNIVERSITE_MANQUANTE:
        return None
    return ALIAS_UNIVERSITES.get(nom, nom)


def _taille_en_pouces(valeur: str) -> float | None:
    """Convertit une taille « 6-4 » (pieds-pouces) en pouces."""
    valeur = (valeur or "").strip()
    if "-" not in valeur:
        return None
    pieds, _, pouces = valeur.partition("-")
    try:
        return int(pieds) * 12 + int(pouces)
    except ValueError:
        return None


def _age_saison(birth_date: str, annee_reference: int = 2021) -> float | None:
    """Âge approximatif au 1er septembre de la saison."""
    bd = (birth_date or "").strip()
    if len(bd) != 10:
        return None
    try:
        annee, mois, jour = (int(p) for p in bd.split("-"))
    except ValueError:
        return None
    return round(annee_reference + 8 / 12 - (annee + (mois - 1) / 12 + jour / 365), 1)


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


def charger_joueurs(chemin: str) -> dict[str, dict]:
    """Charge players.csv -> {nflId: {...}}."""
    joueurs = {}
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            nfl_id = ligne["nflId"].strip()
            if not nfl_id:
                continue
            poids = ligne.get("weight", "").strip()
            joueurs[nfl_id] = {
                "nflId": nfl_id,
                "nom": html.unescape(ligne.get("displayName", "").strip()),
                "universite": normaliser_universite(ligne.get("collegeName")),
                "poste": ligne.get("officialPosition", "").strip(),
                "taille_pouces": _taille_en_pouces(ligne.get("height", "")),
                "poids": float(poids) if poids and poids != "NA" else None,
                "age": _age_saison(ligne.get("birthDate", "")),
            }
    return joueurs


def charger_scouting(chemin: str) -> dict[str, dict]:
    """Agrège pffScoutingData.csv par joueur.

    Produit, pour chaque joueur : le décompte de snaps par rôle, sa production
    défensive (sacks/hits/hurries) et, s'il bloque, la pression concédée.
    """
    agg: dict[str, dict] = {}

    def _nouveau() -> dict:
        return {
            "snaps_par_role": Counter(),
            "snaps": 0,
            # Production défensive (pass rush)
            "sacks": 0,
            "hits": 0,
            "hurries": 0,
            # Protection concédée (pass block)
            "sacks_concedes": 0,
            "hits_concedes": 0,
            "hurries_concedes": 0,
            "battu": 0,
            "snaps_double_equipe": 0,
            "positions": Counter(),
        }

    with open(chemin, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        for ligne in lecteur:
            nfl_id = ligne["nflId"].strip()
            if not nfl_id or nfl_id == "NA":
                continue
            a = agg.get(nfl_id)
            if a is None:
                a = agg[nfl_id] = _nouveau()

            role = ligne["pff_role"].strip()
            a["snaps_par_role"][role] += 1
            a["snaps"] += 1
            pos = ligne.get("pff_positionLinedUp", "").strip()
            if pos and pos != "NA":
                a["positions"][pos] += 1

            if ligne.get("pff_sack") == "1":
                a["sacks"] += 1
            if ligne.get("pff_hit") == "1":
                a["hits"] += 1
            if ligne.get("pff_hurry") == "1":
                a["hurries"] += 1
            if ligne.get("pff_sackAllowed") == "1":
                a["sacks_concedes"] += 1
            if ligne.get("pff_hitAllowed") == "1":
                a["hits_concedes"] += 1
            if ligne.get("pff_hurryAllowed") == "1":
                a["hurries_concedes"] += 1
            if ligne.get("pff_beatenByDefender") == "1":
                a["battu"] += 1

    for a in agg.values():
        if a["snaps_par_role"]:
            a["role_dominant"] = a["snaps_par_role"].most_common(1)[0][0]
        else:
            a["role_dominant"] = None
        a["position_dominante"] = (
            a["positions"].most_common(1)[0][0] if a["positions"] else None
        )
    return agg


def charger_roles_par_action(chemin: str) -> dict[tuple[str, str], dict[str, str]]:
    """Rôle PFF de chaque joueur sur chaque action : {(gameId, playId): {nflId: rôle}}.

    Nécessaire au calcul de la séparation : il faut savoir qui couvre qui.
    On distingue les receveurs en route (« Pass Route ») des défenseurs en
    couverture (« Coverage ») — mesurer la distance entre un bloqueur et un
    rusher n'aurait pas le même sens.
    """
    roles: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            nfl_id = ligne["nflId"].strip()
            if not nfl_id or nfl_id == "NA":
                continue
            cle = (ligne["gameId"].strip(), ligne["playId"].strip())
            roles[cle][nfl_id] = ligne["pff_role"].strip()
    return dict(roles)


def charger_actions(chemin: str) -> dict[tuple[str, str], dict]:
    """Charge plays.csv -> {(gameId, playId): contexte}."""
    actions = {}
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            cle = (ligne["gameId"].strip(), ligne["playId"].strip())
            actions[cle] = {
                "resultat_passe": ligne.get("passResult", "").strip(),
                "yards": _entier(ligne.get("playResult")),
                "down": _entier(ligne.get("down")),
                "yards_a_faire": _entier(ligne.get("yardsToGo")),
                "formation": ligne.get("offenseFormation", "").strip(),
                "couverture": ligne.get("pff_passCoverage", "").strip(),
                "type_couverture": ligne.get("pff_passCoverageType", "").strip(),
                "play_action": ligne.get("pff_playAction") == "1",
            }
    return actions


def _entier(valeur) -> int | None:
    try:
        return int(str(valeur).strip())
    except (TypeError, ValueError):
        return None


def charger_matchs(chemin: str) -> dict[str, dict]:
    """Charge games.csv -> {gameId: {semaine, ...}}."""
    matchs = {}
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            matchs[ligne["gameId"].strip()] = {
                "semaine": _entier(ligne.get("week")),
                "domicile": ligne.get("homeTeamAbbr", "").strip(),
                "visiteur": ligne.get("visitorTeamAbbr", "").strip(),
            }
    return matchs


# ---------------------------------------------------------------------------
# Rapport de nettoyage
# ---------------------------------------------------------------------------


def rapport_nettoyage(
    joueurs: dict[str, dict],
    retenus: list[dict],
    min_joueurs_universite: int,
    min_snaps: int,
) -> dict:
    """Construit un rapport de traçabilité du nettoyage."""
    sans_universite = sum(1 for j in joueurs.values() if not j["universite"])
    universites = Counter(j["universite"] for j in retenus)
    return {
        "joueurs_bruts": len(joueurs),
        "joueurs_sans_universite": sans_universite,
        "joueurs_retenus": len(retenus),
        "universites_retenues": len(universites),
        "min_joueurs_universite": min_joueurs_universite,
        "min_snaps": min_snaps,
        "repartition_universites": dict(universites.most_common()),
    }


def chemins_donnees(racine: str) -> dict[str, str]:
    """Construit les chemins vers les fichiers sources."""
    d = os.path.join(racine, "data")
    return {
        "joueurs": os.path.join(d, "players.csv"),
        "scouting": os.path.join(d, "pffScoutingData.csv"),
        "actions": os.path.join(d, "plays.csv"),
        "matchs": os.path.join(d, "games.csv"),
        "tracking": os.path.join(d, "tracking"),
    }
