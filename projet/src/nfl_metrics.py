"""
Score de performance des joueurs NFL, par poste puis par université.

PRINCIPE — transposition directe du projet « universités »
----------------------------------------------------------
Le projet d'origine notait un diplômé par percentile *à l'intérieur de son
domaine professionnel*, afin de ne pas comparer un salaire de la tech à un
salaire du secteur social. On applique exactement la même précaution ici : un
joueur est noté par percentile *à l'intérieur de son groupe de postes*. Un
pass rusher et un offensive tackle n'ont ni les mêmes statistiques ni les
mêmes échelles — les comparer directement n'aurait aucun sens.

COMPOSITION DU SCORE (0-100)
----------------------------
  Production   50 %  indicateur propre au poste (voir ci-dessous)
  Athlétisme   25 %  vitesse de pointe + accélération de pointe (tracking)
  Temps de jeu 25 %  nombre de snaps — un entraîneur fait jouer ses meilleurs

Indicateur de production selon le rôle PFF réellement tenu :

  Pass Rush    taux de pression générée  = (sacks + hits + hurries) / snaps
  Protection   taux de pression concédée = (sacks + hits + hurries) concédés
                                           / snaps          [sens inversé]
  Couverture   distance au receveur le plus proche au lâcher [sens inversé]
  Réception    séparation obtenue au lâcher
  Quarterback  efficacité = taux de complétion − taux de sack
                            − 2 x taux d'interception

AGRÉGATION PAR UNIVERSITÉ
-------------------------
La moyenne brute par université est trompeuse : la médiane est de 3 joueurs
par établissement. On applique donc un shrinkage bayésien empirique
(cf. nfl_stats.shrinkage_empirique) qui tire les petits effectifs vers la
moyenne générale. Les classements publiés reposent sur le score régularisé.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from . import nfl_data, nfl_stats as st

PONDERATIONS = {"production": 0.50, "athletisme": 0.25, "temps_de_jeu": 0.25}

# Seuils par défaut.
MIN_SNAPS = 50
MIN_ACTIONS_SEPARATION = 10
MIN_JOUEURS_UNIVERSITE = 5
MIN_JOUEURS_UNIVERSITE_POSTE = 3


# ---------------------------------------------------------------------------
# 1. Indicateur de production par rôle
# ---------------------------------------------------------------------------


def _efficacite_qb(nfl_id: str, roles_par_action: dict, actions: dict) -> dict | None:
    """Efficacité de passe d'un quarterback, à partir des résultats d'action."""
    resultats = Counter()
    for cle, roles in roles_par_action.items():
        if roles.get(nfl_id) != "Pass":
            continue
        ctx = actions.get(cle)
        if ctx:
            resultats[ctx["resultat_passe"]] += 1
    total = sum(resultats.values())
    if total == 0:
        return None
    # « R » (scramble) est une action courue : comptée dans le total mais
    # ni réussie ni sanctionnée.
    taux_completion = resultats["C"] / total
    taux_sack = resultats["S"] / total
    taux_interception = resultats["IN"] / total
    return {
        "tentatives": total,
        "taux_completion": taux_completion,
        "taux_sack": taux_sack,
        "taux_interception": taux_interception,
        "efficacite": taux_completion - taux_sack - 2 * taux_interception,
    }


def calculer_production(
    nfl_id: str,
    role: str,
    scouting: dict,
    separation: dict,
    roles_par_action: dict,
    actions: dict,
) -> tuple[float | None, dict]:
    """Retourne (valeur_production, détails) pour un joueur selon son rôle."""
    sc = scouting.get(nfl_id, {})
    snaps_role = sc.get("snaps_par_role", Counter()).get(role, 0)
    details: dict = {}

    if role == "Pass Rush":
        if snaps_role <= 0:
            return None, details
        pressions = sc.get("sacks", 0) + sc.get("hits", 0) + sc.get("hurries", 0)
        details = {
            "sacks": sc.get("sacks", 0),
            "hits": sc.get("hits", 0),
            "hurries": sc.get("hurries", 0),
            "pressions": pressions,
            "snaps_rush": snaps_role,
        }
        return pressions / snaps_role, details

    if role == "Pass Block":
        if snaps_role <= 0:
            return None, details
        concedees = (
            sc.get("sacks_concedes", 0)
            + sc.get("hits_concedes", 0)
            + sc.get("hurries_concedes", 0)
        )
        details = {
            "sacks_concedes": sc.get("sacks_concedes", 0),
            "hits_concedes": sc.get("hits_concedes", 0),
            "hurries_concedes": sc.get("hurries_concedes", 0),
            "pressions_concedees": concedees,
            "battu": sc.get("battu", 0),
            "snaps_protection": snaps_role,
        }
        return concedees / snaps_role, details

    if role in ("Coverage", "Pass Route"):
        sep = separation.get(nfl_id)
        if not sep or sep["n_actions"] < MIN_ACTIONS_SEPARATION:
            return None, details
        details = {
            "separation_mediane": sep["separation_mediane"],
            "separation_moyenne": sep["separation_moyenne"],
            "n_actions_mesurees": sep["n_actions"],
        }
        return sep["separation_mediane"], details

    if role == "Pass":
        eff = _efficacite_qb(nfl_id, roles_par_action, actions)
        if not eff:
            return None, details
        return eff["efficacite"], dict(eff)

    return None, details


# ---------------------------------------------------------------------------
# 2. Construction de la table des joueurs
# ---------------------------------------------------------------------------


def construire_table(
    joueurs: dict,
    scouting: dict,
    athletisme: dict,
    separation: dict,
    roles_par_action: dict,
    actions: dict,
    min_snaps: int = MIN_SNAPS,
) -> tuple[list[dict], dict]:
    """Assemble une ligne par joueur retenu. Retourne (lignes, diagnostic)."""
    lignes: list[dict] = []
    exclusions = Counter()

    for nfl_id, j in joueurs.items():
        if not j["universite"]:
            exclusions["universite_manquante"] += 1
            continue

        sc = scouting.get(nfl_id)
        if not sc or not sc.get("role_dominant"):
            exclusions["aucun_snap"] += 1
            continue

        snaps = sc["snaps"]
        if snaps < min_snaps:
            exclusions["snaps_insuffisants"] += 1
            continue

        role = sc["role_dominant"]
        ath = athletisme.get(nfl_id)
        if not ath:
            exclusions["tracking_absent"] += 1
            continue

        production, details = calculer_production(
            nfl_id, role, scouting, separation, roles_par_action, actions
        )
        if production is None:
            exclusions["production_indisponible"] += 1
            continue

        lignes.append(
            {
                "nflId": nfl_id,
                "nom": j["nom"],
                "universite": j["universite"],
                "poste": j["poste"],
                "role": role,
                "groupe": nfl_data.GROUPES.get(role, role),
                "position_alignement": sc.get("position_dominante"),
                "taille_pouces": j["taille_pouces"],
                "poids": j["poids"],
                "age": j["age"],
                "snaps": snaps,
                "vitesse_max": ath["vitesse_max"],
                "accel_max": ath["accel_max"],
                "production": production,
                **details,
            }
        )

    return lignes, dict(exclusions)


# ---------------------------------------------------------------------------
# 3. Scores en percentile intra-poste
# ---------------------------------------------------------------------------


def calculer_scores(lignes: list[dict]) -> tuple[list[dict], dict]:
    """Ajoute les sous-scores et le score global.

    Normalisation à deux niveaux : les percentiles sont calculés sur la
    famille de postes fine (WR / TE / RB plutôt que « Réception »), afin de ne
    comparer que des joueurs dont les statistiques ont la même échelle. Si une
    famille compte moins de MIN_EFFECTIF_FAMILLE joueurs, on retombe sur le
    groupe large pour éviter un percentile calculé sur 2 ou 3 observations.
    """
    # On calcule DEUX jeux de percentiles : un par famille fine, un par rôle
    # complet. Chaque joueur utilise celui de sa famille si elle est assez
    # peuplée, sinon celui de son rôle — qui contient alors tous les joueurs
    # du rôle, et non les seuls « restes ».
    #
    # Ce point est critique : un repli qui ne regrouperait que les joueurs
    # exclus des familles fines créerait des groupes d'une seule personne,
    # automatiquement classée au percentile 100 sur chaque composante.
    par_role: dict[str, list[dict]] = defaultdict(list)
    par_famille: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_role[l["role"]].append(l)
        par_famille[nfl_data.famille_normalisation(l["role"], l["poste"])].append(l)

    pct_par_role = {role: _percentiles(g) for role, g in par_role.items()}
    pct_par_famille = {
        cle: _percentiles(g)
        for cle, g in par_famille.items()
        if len(g) >= nfl_data.MIN_EFFECTIF_FAMILLE
    }

    diagnostic: dict[str, dict] = {}
    for l in lignes:
        role = l["role"]
        cle_fine = nfl_data.famille_normalisation(role, l["poste"])
        if cle_fine in pct_par_famille:
            pcts = pct_par_famille[cle_fine][l["nflId"]]
            l["cle_normalisation"] = cle_fine
            l["famille"] = nfl_data.FAMILLES_POSTES.get(l["poste"], l["poste"])
            l["normalisation_repli"] = False
        else:
            pcts = pct_par_role[role][l["nflId"]]
            l["cle_normalisation"] = role
            l["famille"] = nfl_data.GROUPES.get(role, role)
            l["normalisation_repli"] = True

        pct_prod, pct_vitesse, pct_accel, pct_snaps = pcts
        # Inversion quand « plus bas = mieux » (pression concédée, distance
        # de couverture).
        plus_haut_est_mieux = nfl_data.SENS_PRODUCTION.get(role, True)
        l["score_production"] = (
            pct_prod if plus_haut_est_mieux else 100.0 - pct_prod
        )
        l["score_athletisme"] = (pct_vitesse + pct_accel) / 2.0
        l["score_temps_de_jeu"] = pct_snaps
        l["score_global"] = (
            PONDERATIONS["production"] * l["score_production"]
            + PONDERATIONS["athletisme"] * l["score_athletisme"]
            + PONDERATIONS["temps_de_jeu"] * l["score_temps_de_jeu"]
        )

    for cle, groupe in sorted(par_famille.items()):
        diagnostic[cle] = {
            "n": len(groupe),
            "utilisee": cle in pct_par_famille,
            "production_mediane": st.mediane([l["production"] for l in groupe]),
        }
    diagnostic["_replis"] = {
        "n_joueurs_en_repli": sum(1 for l in lignes if l["normalisation_repli"]),
        "familles_trop_petites": sorted(
            cle for cle, g in par_famille.items()
            if len(g) < nfl_data.MIN_EFFECTIF_FAMILLE
        ),
    }

    return lignes, diagnostic


def _percentiles(groupe: list[dict]) -> dict[str, tuple[float, float, float, float]]:
    """Percentiles des 4 composantes au sein d'un groupe, indexés par nflId."""
    prod = st.rangs_percentiles([l["production"] for l in groupe])
    vitesse = st.rangs_percentiles([l["vitesse_max"] for l in groupe])
    accel = st.rangs_percentiles([l["accel_max"] for l in groupe])
    snaps = st.rangs_percentiles([l["snaps"] for l in groupe])
    return {
        l["nflId"]: (prod[i], vitesse[i], accel[i], snaps[i])
        for i, l in enumerate(groupe)
    }


def categoriser(lignes: list[dict]) -> list[dict]:
    """Classe les joueurs en Faible / Moyen / Élevé (terciles) pour le Chi-2."""
    scores = [l["score_global"] for l in lignes]
    if not scores:
        return lignes
    s1, s2 = st.quantile(scores, 1 / 3), st.quantile(scores, 2 / 3)
    for l in lignes:
        v = l["score_global"]
        l["categorie"] = "Faible" if v < s1 else ("Moyen" if v < s2 else "Élevé")
    return lignes


# ---------------------------------------------------------------------------
# 4. Agrégation par université
# ---------------------------------------------------------------------------


def classement_universites(
    lignes: list[dict],
    min_joueurs: int = MIN_JOUEURS_UNIVERSITE,
) -> dict:
    """Classe les universités sur l'ensemble des postes, avec régularisation."""
    par_univ: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_univ[l["universite"]].append(l)

    eligibles = {u: v for u, v in par_univ.items() if len(v) >= min_joueurs}
    if len(eligibles) < 2:
        return {"applicable": False, "raison": "Moins de 2 universités éligibles"}

    scores_par_univ = {u: [l["score_global"] for l in v] for u, v in eligibles.items()}
    shrink = st.shrinkage_empirique(scores_par_univ)

    tous_scores = [l["score_global"] for v in eligibles.values() for l in v]

    classement = []
    for univ, joueurs_u in eligibles.items():
        scores = [l["score_global"] for l in joueurs_u]
        reste = [
            l["score_global"]
            for u, v in eligibles.items()
            if u != univ
            for l in v
        ]
        moyenne, demi_ic = st.ic95(scores)
        test = st.test_t_welch(scores, reste)
        info_shrink = shrink["groupes"][univ]

        classement.append(
            {
                "universite": univ,
                "n_joueurs": len(joueurs_u),
                "score_brut": moyenne,
                "score_regularise": info_shrink["moyenne_regularisee"],
                "retrait_shrinkage": info_shrink["retrait"],
                "ic95_bas": moyenne - demi_ic if demi_ic == demi_ic else None,
                "ic95_haut": moyenne + demi_ic if demi_ic == demi_ic else None,
                "p_value_vs_reste": test.get("p_value"),
                "significatif": test.get("significatif", False),
                "cohen_d": st.cohen_d(scores, reste),
                "postes_couverts": len({l["role"] for l in joueurs_u}),
                "repartition_postes": dict(
                    Counter(l["groupe"] for l in joueurs_u).most_common()
                ),
            }
        )

    classement.sort(key=lambda x: x["score_regularise"], reverse=True)
    for rang, ligne in enumerate(classement, 1):
        ligne["rang"] = rang

    return {
        "applicable": True,
        "classement": classement,
        "k_shrinkage": shrink["k"],
        "signal_detectable": shrink["signal_detectable"],
        "moyenne_generale": shrink["moyenne_generale"],
        "variance_intra": shrink["variance_intra"],
        "variance_inter": shrink["variance_inter"],
        "n_universites": len(eligibles),
        "n_joueurs": len(tous_scores),
        "validation_moities": st.validation_moities(scores_par_univ),
    }


def classement_par_poste(
    lignes: list[dict],
    min_joueurs: int = MIN_JOUEURS_UNIVERSITE_POSTE,
) -> dict:
    """Classe les universités séparément pour chaque groupe de postes."""
    par_role: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_role[l["role"]].append(l)

    resultats = {}
    for role in nfl_data.ORDRE_GROUPES:
        groupe = par_role.get(role, [])
        if not groupe:
            continue

        par_univ: dict[str, list[dict]] = defaultdict(list)
        for l in groupe:
            par_univ[l["universite"]].append(l)
        eligibles = {u: v for u, v in par_univ.items() if len(v) >= min_joueurs}

        if len(eligibles) < 2:
            resultats[role] = {
                "applicable": False,
                "raison": f"Moins de 2 universités avec {min_joueurs}+ joueurs",
                "n_joueurs_groupe": len(groupe),
                "n_universites_eligibles": len(eligibles),
            }
            continue

        scores_par_univ = {
            u: [l["score_global"] for l in v] for u, v in eligibles.items()
        }
        shrink = st.shrinkage_empirique(scores_par_univ)
        anova = st.anova_un_facteur(list(scores_par_univ.values()))

        classement = []
        for univ, joueurs_u in eligibles.items():
            scores = [l["score_global"] for l in joueurs_u]
            reste = [
                l["score_global"]
                for u, v in eligibles.items()
                if u != univ
                for l in v
            ]
            moyenne, demi_ic = st.ic95(scores)
            test = st.test_t_welch(scores, reste)
            meilleur = max(joueurs_u, key=lambda l: l["score_global"])
            classement.append(
                {
                    "universite": univ,
                    "n_joueurs": len(joueurs_u),
                    "score_brut": moyenne,
                    "score_regularise": shrink["groupes"][univ]["moyenne_regularisee"],
                    "ic95_bas": moyenne - demi_ic if demi_ic == demi_ic else None,
                    "ic95_haut": moyenne + demi_ic if demi_ic == demi_ic else None,
                    "p_value_vs_reste": test.get("p_value"),
                    "significatif": test.get("significatif", False),
                    "cohen_d": st.cohen_d(scores, reste),
                    "meilleur_joueur": meilleur["nom"],
                    "meilleur_joueur_score": meilleur["score_global"],
                    "production_moyenne": st.moyenne(
                        [l["production"] for l in joueurs_u]
                    ),
                }
            )

        classement.sort(key=lambda x: x["score_regularise"], reverse=True)
        for rang, ligne in enumerate(classement, 1):
            ligne["rang"] = rang

        resultats[role] = {
            "applicable": True,
            "groupe": nfl_data.GROUPES.get(role, role),
            "libelle_production": nfl_data.LIBELLE_PRODUCTION.get(role, "Production"),
            "sens_production": (
                "plus haut = mieux"
                if nfl_data.SENS_PRODUCTION.get(role, True)
                else "plus bas = mieux"
            ),
            "classement": classement,
            "anova": anova,
            "k_shrinkage": shrink["k"],
            "signal_detectable": shrink["signal_detectable"],
            "moyenne_generale": shrink["moyenne_generale"],
            "n_joueurs_groupe": len(groupe),
            "n_universites_eligibles": len(eligibles),
            "validation_moities": st.validation_moities(scores_par_univ),
        }

    return resultats


def meilleurs_joueurs_par_poste(lignes: list[dict], top: int = 10) -> dict:
    """Top joueurs de chaque groupe de postes, avec leur université."""
    par_role: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_role[l["role"]].append(l)

    resultats = {}
    for role in nfl_data.ORDRE_GROUPES:
        groupe = sorted(
            par_role.get(role, []), key=lambda l: l["score_global"], reverse=True
        )
        resultats[role] = groupe[:top]
    return resultats


def tests_globaux(lignes: list[dict], classement: dict) -> dict:
    """Tests statistiques sur l'effet « université », tous postes confondus."""
    par_univ: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_univ[l["universite"]].append(l)
    eligibles = {
        u: v for u, v in par_univ.items() if len(v) >= MIN_JOUEURS_UNIVERSITE
    }

    resultats: dict = {}

    # ANOVA : les moyennes diffèrent-elles entre universités ?
    resultats["anova"] = st.anova_un_facteur(
        [[l["score_global"] for l in v] for v in eligibles.values()]
    )

    # Chi-2 : université x catégorie de performance.
    categories = ["Faible", "Moyen", "Élevé"]
    universites = sorted(eligibles)
    table = [
        [
            sum(1 for l in eligibles[u] if l.get("categorie") == c)
            for c in categories
        ]
        for u in universites
    ]
    resultats["chi2"] = st.chi2_independance(table)
    resultats["chi2"]["universites"] = universites
    resultats["chi2"]["categories"] = categories

    # Spearman : corrélation entre le rang de l'université et le score
    # individuel. ATTENTION — ce test est CIRCULAIRE : le rang est lui-même
    # calculé à partir de ces mêmes scores. Il ne constitue donc pas une
    # preuve de l'effet université, seulement une mesure descriptive de la
    # dispersion du classement. Le test non circulaire est la validation par
    # moitiés (`validation_moities`).
    if classement.get("applicable"):
        rang_par_univ = {
            c["universite"]: classement["n_universites"] - c["rang"] + 1
            for c in classement["classement"]
        }
        xs, ys = [], []
        for u, v in eligibles.items():
            if u in rang_par_univ:
                for l in v:
                    xs.append(rang_par_univ[u])
                    ys.append(l["score_global"])
        resultats["spearman"] = st.spearman(xs, ys) if len(xs) >= 3 else {
            "applicable": False
        }
        resultats["spearman"]["circulaire"] = True
    else:
        resultats["spearman"] = {"applicable": False}

    # Validation par moitiés : test NON circulaire de reproductibilité.
    resultats["validation_moities"] = st.validation_moities(
        {u: [l["score_global"] for l in v] for u, v in eligibles.items()}
    )

    # Validation de face : le score retrouve-t-il les joueurs d'élite ?
    resultats["validation_faciale"] = validation_faciale(lignes)

    return resultats


# Joueurs reconnus comme élite à leur poste sur la saison 2021 (sélections
# Pro Bowl / All-Pro). Sert de contrôle externe : un score de performance
# crédible doit les placer dans le haut de leur groupe.
ELITE_2021 = {
    "Pass Rush": [
        "Shaquil Barrett", "Trey Hendrickson", "Myles Garrett", "Matt Judon",
        "Cameron Jordan", "Aaron Donald", "Maxx Crosby", "Harold Landry",
    ],
    "Pass Block": [
        "Tristan Wirfs", "Trent Williams", "Corey Linsley", "Joe Thuney",
        "Zack Martin", "Jason Kelce", "Lane Johnson", "Quenton Nelson",
    ],
    "Coverage": [
        "Xavien Howard", "Marshon Lattimore", "Marlon Humphrey",
        "Tre'Davious White", "Jalen Ramsey", "J.C. Jackson", "Jaire Alexander",
    ],
    "Pass": [
        "Tom Brady", "Patrick Mahomes", "Josh Allen", "Aaron Rodgers",
        "Matthew Stafford", "Joe Burrow", "Dak Prescott",
    ],
}


def validation_faciale(lignes: list[dict]) -> dict:
    """Vérifie que les joueurs d'élite connus ressortent en haut du classement.

    Contrôle de validité externe : si le score était du bruit, les Pro Bowlers
    se répartiraient uniformément (percentile moyen attendu ~50).
    """
    par_role: dict[str, list[dict]] = defaultdict(list)
    for l in lignes:
        par_role[l["role"]].append(l)

    resultats = {}
    for role, noms in ELITE_2021.items():
        groupe = par_role.get(role, [])
        if len(groupe) < 5:
            continue
        scores = [l["score_global"] for l in groupe]
        percentiles = st.rangs_percentiles(scores)
        index = {l["nom"]: percentiles[i] for i, l in enumerate(groupe)}
        trouves = {n: index[n] for n in noms if n in index}
        if not trouves:
            continue
        resultats[role] = {
            "groupe": nfl_data.GROUPES.get(role, role),
            "n_elite_trouves": len(trouves),
            "n_elite_cherches": len(noms),
            "percentile_moyen": st.moyenne(list(trouves.values())),
            "part_dans_top_tiers": sum(
                1 for v in trouves.values() if v >= 66.7
            ) / len(trouves),
            "detail": {n: round(v, 1) for n, v in sorted(
                trouves.items(), key=lambda x: -x[1]
            )},
        }

    if resultats:
        tous = [r["percentile_moyen"] for r in resultats.values()]
        resultats["_global"] = {
            "percentile_moyen_elite": st.moyenne(tous),
            "attendu_si_aleatoire": 50.0,
        }
    return resultats
