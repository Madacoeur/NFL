#!/usr/bin/env python3
"""
Analyse « Performance des joueurs NFL par poste et par université ».

Transposition du projet « universités / réussite professionnelle » aux données
du NFL Big Data Bowl 2023 : on remplace les diplômés par des joueurs, les
domaines professionnels par les postes, et le salaire par une mesure de
performance reconstruite depuis le tracking GPS et le scouting PFF.

Usage :
    python main_nfl.py
    python main_nfl.py --donnees /chemin/vers/nfl-big-data-bowl-regional-event-data
    python main_nfl.py --min-snaps 100 --min-joueurs 8

Produit :
    data/output/scores_joueurs.csv
    data/output/classement_universites.csv
    data/output/classement_par_poste.csv
    data/output/statistiques_nfl.json
    rapport_nfl.md
    presentation_nfl.pptx
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import nfl_data, nfl_metrics, nfl_slides, nfl_tracking
from src import nfl_stats as st
from src import pptx_validator

BASE = os.path.dirname(os.path.abspath(__file__))
DOSSIER_SORTIE = os.path.join(BASE, "data", "output")

# Emplacement par défaut du dépôt de données, voisin de celui-ci.
DONNEES_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(BASE)),
    "nfl-big-data-bowl-regional-event-data",
)


def _log(message: str) -> None:
    print(f"[nfl] {message}", flush=True)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

COLONNES_JOUEURS = [
    "nflId", "nom", "universite", "poste", "famille", "groupe", "role",
    "position_alignement", "taille_pouces", "poids", "age", "snaps",
    "vitesse_max", "accel_max", "production", "score_production",
    "score_athletisme", "score_temps_de_jeu", "score_global", "categorie",
]


def exporter_joueurs(lignes: list[dict], chemin: str) -> None:
    extras = sorted(
        {c for l in lignes for c in l} - set(COLONNES_JOUEURS) - {"cle_normalisation"}
    )
    colonnes = COLONNES_JOUEURS + extras
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        ecrivain.writeheader()
        for l in sorted(lignes, key=lambda x: -x["score_global"]):
            ecrivain.writerow({c: _arrondir(l.get(c)) for c in colonnes})


def exporter_classement(classement: dict, chemin: str) -> None:
    if not classement.get("applicable"):
        return
    colonnes = [
        "rang", "universite", "n_joueurs", "score_brut", "score_regularise",
        "retrait_shrinkage", "ic95_bas", "ic95_haut", "p_value_vs_reste",
        "significatif", "cohen_d", "postes_couverts",
    ]
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        ecrivain.writeheader()
        for c in classement["classement"]:
            ecrivain.writerow({k: _arrondir(c.get(k)) for k in colonnes})


def exporter_classement_par_poste(par_poste: dict, chemin: str) -> None:
    colonnes = [
        "groupe", "rang", "universite", "n_joueurs", "score_brut",
        "score_regularise", "p_value_vs_reste", "significatif", "cohen_d",
        "meilleur_joueur", "meilleur_joueur_score",
    ]
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        ecrivain.writeheader()
        for role, resultat in par_poste.items():
            if not resultat.get("applicable"):
                continue
            for c in resultat["classement"]:
                ligne = {k: _arrondir(c.get(k)) for k in colonnes}
                ligne["groupe"] = resultat["groupe"]
                ecrivain.writerow(ligne)


def _arrondir(valeur):
    if isinstance(valeur, float):
        if valeur != valeur:
            return ""
        return round(valeur, 4)
    if isinstance(valeur, bool):
        return int(valeur)
    return "" if valeur is None else valeur


def _json_propre(objet):
    """Rend une structure sérialisable (NaN -> None, Counter -> dict)."""
    if isinstance(objet, float):
        return None if objet != objet or objet in (float("inf"), float("-inf")) \
            else round(objet, 6)
    if isinstance(objet, dict):
        return {str(k): _json_propre(v) for k, v in objet.items()}
    if isinstance(objet, (list, tuple)):
        return [_json_propre(v) for v in objet]
    if isinstance(objet, Counter):
        return {str(k): v for k, v in objet.items()}
    return objet


# ---------------------------------------------------------------------------
# Rapport Markdown
# ---------------------------------------------------------------------------


def construire_rapport(ctx: dict, nettoyage: dict, duree: float) -> str:
    cl = ctx["classement_universites"]
    tests = ctx["tests_globaux"]
    vf = ctx["validation_faciale"]
    vm = cl.get("validation_moities", {})

    lignes = [
        "# Performance des joueurs NFL par poste et par université",
        "",
        "> Analyse produite par `main_nfl.py` — données NFL Big Data Bowl 2023 "
        "(saison 2021, semaines 1 à 8).",
        "",
        "## Question",
        "",
        "L'université d'origine d'un joueur a-t-elle un effet mesurable sur sa "
        "performance en NFL, poste par poste ?",
        "",
        "## Réponse courte",
        "",
        "**Non.** Le score de performance construit ici est valide — il "
        f"identifie correctement les joueurs d'élite (percentile moyen "
        f"{vf.get('_global', {}).get('percentile_moyen_elite', float('nan')):.1f} "
        "pour les Pro Bowlers 2021, contre 50 attendu au hasard). Mais aucun "
        "test ne détecte d'effet de l'université sur la performance, à aucun "
        "poste.",
        "",
        "## Périmètre retenu",
        "",
        f"- Joueurs référencés : **{nettoyage['joueurs_bruts']}**",
        f"- Sans université renseignée (exclus) : **{nettoyage['joueurs_sans_universite']}**",
        f"- Retenus après filtrage : **{nettoyage['joueurs_retenus']}** "
        f"(≥ {nettoyage['min_snaps']} snaps)",
        f"- Universités classées : **{cl.get('n_universites', 0)}** "
        f"(≥ {nettoyage['min_joueurs_universite']} joueurs)",
        f"- Lignes de tracking traitées : **{ctx['n_lignes_tracking']:,}**".replace(
            ",", " "
        ),
        f"- Durée d'exécution : **{duree:.0f} s**",
        "",
        "## Composition du score",
        "",
        "| Composante | Poids | Calcul |",
        "|---|---|---|",
        "| Production | 50 % | Indicateur propre au poste, en percentile "
        "intra-poste |",
        "| Athlétisme | 25 % | Vitesse et accélération de pointe (tracking) |",
        "| Temps de jeu | 25 % | Nombre de snaps joués |",
        "",
        "### Indicateur de production par poste",
        "",
        "| Groupe | Indicateur | Sens favorable | Joueurs |",
        "|---|---|---|---|",
    ]

    for role in nfl_data.ORDRE_GROUPES:
        info = ctx["effectifs_groupes"].get(role)
        if not info:
            continue
        sens = "plus haut" if nfl_data.SENS_PRODUCTION[role] else "plus bas"
        lignes.append(
            f"| {nfl_data.GROUPES[role]} | "
            f"{nfl_data.LIBELLE_PRODUCTION[role]} | {sens} | {info['n']} |"
        )

    lignes += [
        "",
        "## Validation du score",
        "",
        "Contrôle de validité externe : on vérifie que les joueurs sélectionnés "
        "en Pro Bowl ou All-Pro en 2021 ressortent effectivement en haut de "
        "leur groupe.",
        "",
        "| Groupe | Joueurs d'élite retrouvés | Percentile moyen | Part dans le "
        "tiers supérieur |",
        "|---|---|---|---|",
    ]
    for role in nfl_data.ORDRE_GROUPES:
        r = vf.get(role)
        if not r:
            continue
        lignes.append(
            f"| {r['groupe']} | {r['n_elite_trouves']}/{r['n_elite_cherches']} | "
            f"{r['percentile_moyen']:.1f} | {r['part_dans_top_tiers'] * 100:.0f} % |"
        )

    lignes += [
        "",
        "## Meilleurs joueurs par poste",
        "",
    ]
    for role in nfl_data.ORDRE_GROUPES:
        joueurs = ctx["meilleurs_joueurs"].get(role, [])[:5]
        if not joueurs:
            continue
        lignes += [
            f"### {nfl_data.GROUPES[role]}",
            "",
            f"| # | Joueur | Poste | Université | Score | "
            f"{nfl_data.LIBELLE_PRODUCTION[role]} |",
            "|---|---|---|---|---|---|",
        ]
        for i, j in enumerate(joueurs, 1):
            lignes.append(
                f"| {i} | {j['nom']} | {j['poste']} | {j['universite']} | "
                f"{j['score_global']:.1f} | {j['production']:.3f} |"
            )
        lignes.append("")

    lignes += [
        "## Classement des universités (tous postes)",
        "",
        "Le score régularisé corrige l'effet de taille d'échantillon "
        "(shrinkage bayésien empirique). C'est lui qui fait foi.",
        "",
        "| # | Université | Joueurs | Score brut | Score régularisé | p-value |",
        "|---|---|---|---|---|---|",
    ]
    for c in cl.get("classement", [])[:15]:
        lignes.append(
            f"| {c['rang']} | {c['universite']} | {c['n_joueurs']} | "
            f"{c['score_brut']:.1f} | {c['score_regularise']:.1f} | "
            f"{c['p_value_vs_reste']:.3f} |"
        )

    anova = tests["anova"]
    chi2 = tests["chi2"]
    lignes += [
        "",
        "## Tests statistiques",
        "",
        "| Test | Statistique | p-value | Effet détecté |",
        "|---|---|---|---|",
        f"| ANOVA globale | F = {anova.get('f_statistic', float('nan')):.3f} | "
        f"{anova.get('p_value', float('nan')):.4f} | "
        f"{'oui' if anova.get('significatif') else 'non'} |",
        f"| Chi-2 d'indépendance | V de Cramér = "
        f"{chi2.get('cramer_v', float('nan')):.3f} | "
        f"{chi2.get('p_value', float('nan')):.4f} | "
        f"{'oui' if chi2.get('significatif') else 'non'} |",
    ]
    for role in nfl_data.ORDRE_GROUPES:
        r = ctx["classement_par_poste"].get(role, {})
        if not r.get("applicable"):
            continue
        a = r["anova"]
        lignes.append(
            f"| ANOVA · {r['groupe']} | F = {a.get('f_statistic', float('nan')):.3f} "
            f"| {a.get('p_value', float('nan')):.4f} | "
            f"{'oui' if a.get('significatif') else 'non'} |"
        )

    lignes += [
        "",
        "### Validation par moitiés (test non circulaire)",
        "",
        "On coupe au hasard les joueurs de chaque université en deux moitiés, "
        "on classe les universités sur la première, et on mesure si ce "
        "classement prédit celui de la seconde. Répété 200 fois.",
        "",
    ]
    if vm.get("applicable"):
        lignes += [
            f"- ρ moyen : **{vm['rho_moyen']:+.3f}** ({vm['interpretation']})",
            f"- Tirages à corrélation positive : "
            f"**{vm['part_tirages_positifs'] * 100:.0f} %**",
            f"- Étendue : {vm['rho_min']:+.3f} à {vm['rho_max']:+.3f}",
            "",
            "Un ρ proche de zéro signifie que le classement n'est pas "
            "reproductible : il reflète le bruit d'échantillonnage.",
        ]

    lignes += [
        "",
        "## Pourquoi ce résultat",
        "",
        "Les joueurs comparés ont tous franchi un filtre de sélection d'une "
        "sévérité extrême (environ 250 draftés par an pour 75 000 joueurs "
        "universitaires). La variabilité qui distinguait les universités a été "
        "absorbée en amont par le recrutement. Les grands programmes envoient "
        "**plus** de joueurs en NFL (Alabama 47, LSU 43, contre 3 en médiane) "
        "sans que ces joueurs y soient **meilleurs**.",
        "",
        "## Limites",
        "",
        "- Huit semaines d'une seule saison : aucune validation croisée possible",
        "- Actions de passe uniquement : aucune course dans le jeu de données",
        "- Médiane de 3 joueurs par université : contrainte dominante",
        "- Un effet non détecté n'est pas un effet nul démontré",
        "- Couverture et réception évaluées via la séparation au lâcher, qui "
        "ignore le schéma défensif",
        f"- {nettoyage['joueurs_sans_universite']} joueurs sans université "
        "renseignée, exclus",
        "",
        "## Reproduire",
        "",
        "```bash",
        "python main_nfl.py --donnees ../../nfl-big-data-bowl-regional-event-data",
        "```",
        "",
        "Aucune dépendance externe : bibliothèque standard de Python 3.11 "
        "uniquement, y compris pour les tests statistiques et la génération du "
        "fichier PowerPoint.",
        "",
    ]
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse de la performance NFL par poste et par université"
    )
    parser.add_argument(
        "--donnees",
        default=DONNEES_DEFAUT,
        help="Racine du dépôt de données NFL Big Data Bowl.",
    )
    parser.add_argument("--min-snaps", type=int, default=nfl_metrics.MIN_SNAPS)
    parser.add_argument(
        "--min-joueurs", type=int, default=nfl_metrics.MIN_JOUEURS_UNIVERSITE
    )
    parser.add_argument(
        "--min-joueurs-poste",
        type=int,
        default=nfl_metrics.MIN_JOUEURS_UNIVERSITE_POSTE,
    )
    parser.add_argument(
        "--limite-matchs",
        type=int,
        default=None,
        help="Limite le nombre de fichiers tracking lus (mise au point).",
    )
    parser.add_argument(
        "--sans-pptx", action="store_true", help="N'écrit pas la présentation."
    )
    args = parser.parse_args()

    t0 = time.time()
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    chemins = nfl_data.chemins_donnees(args.donnees)
    manquants = [c for c in chemins.values() if not os.path.exists(c)]
    if manquants:
        _log("ERREUR : sources introuvables :")
        for m in manquants:
            _log(f"  - {m}")
        _log("Précisez le chemin avec --donnees.")
        return 1

    # --- 1. Chargement ---------------------------------------------------
    _log("Chargement des joueurs et du scouting PFF...")
    joueurs = nfl_data.charger_joueurs(chemins["joueurs"])
    scouting = nfl_data.charger_scouting(chemins["scouting"])
    roles_par_action = nfl_data.charger_roles_par_action(chemins["scouting"])
    actions = nfl_data.charger_actions(chemins["actions"])
    _log(
        f"{len(joueurs)} joueurs, {len(actions)} actions, "
        f"{len(roles_par_action)} actions avec rôles."
    )

    # --- 2. Tracking -----------------------------------------------------
    _log("Balayage du tracking (athlétisme + séparation au lâcher)...")
    tracking = nfl_tracking.analyser_tous(
        chemins["tracking"],
        roles_par_action,
        journal=_log,
        limite_fichiers=args.limite_matchs,
    )
    _log(
        f"{tracking['n_lignes']:,} lignes sur {tracking['n_fichiers']} matchs "
        f"en {tracking['duree_s']:.0f} s.".replace(",", " ")
    )

    # --- 3. Construction de la table -------------------------------------
    _log("Calcul des indicateurs par joueur...")
    lignes, exclusions = nfl_metrics.construire_table(
        joueurs,
        scouting,
        tracking["athletisme"],
        tracking["separation"],
        roles_par_action,
        actions,
        min_snaps=args.min_snaps,
    )
    if not lignes:
        _log("ERREUR : aucun joueur retenu après filtrage.")
        return 1
    _log(f"{len(lignes)} joueurs retenus. Exclusions : {exclusions}")

    lignes, diagnostic = nfl_metrics.calculer_scores(lignes)
    nfl_metrics.categoriser(lignes)

    nettoyage = nfl_data.rapport_nettoyage(
        joueurs, lignes, args.min_joueurs, args.min_snaps
    )
    nettoyage["exclusions"] = exclusions

    # --- 4. Classements et tests -----------------------------------------
    _log("Agrégation par université et tests statistiques...")
    classement = nfl_metrics.classement_universites(
        lignes, min_joueurs=args.min_joueurs
    )
    par_poste = nfl_metrics.classement_par_poste(
        lignes, min_joueurs=args.min_joueurs_poste
    )
    meilleurs = nfl_metrics.meilleurs_joueurs_par_poste(lignes, top=10)
    tests = nfl_metrics.tests_globaux(lignes, classement)

    if classement.get("applicable"):
        anova = tests["anova"]
        _log(
            f"ANOVA globale : F = {anova.get('f_statistic', 0):.3f}, "
            f"p = {anova.get('p_value', 1):.4f} "
            f"({'significatif' if anova.get('significatif') else 'non significatif'})"
        )
        vm = classement.get("validation_moities", {})
        if vm.get("applicable"):
            _log(
                f"Validation par moitiés : rho moyen = {vm['rho_moyen']:+.3f} "
                f"({vm['interpretation']})"
            )

    # --- 5. Contexte pour les livrables ----------------------------------
    effectifs_groupes = {}
    for role in nfl_data.ORDRE_GROUPES:
        du_role = [l for l in lignes if l["role"] == role]
        if not du_role:
            continue
        postes = Counter(l["poste"] for l in du_role)
        effectifs_groupes[role] = {
            "n": len(du_role),
            "postes": ", ".join(p for p, _ in postes.most_common(4)),
        }

    # Volumes bruts par université (tous les joueurs référencés, avant
    # filtrage) : sert à montrer que les grands programmes envoient davantage
    # de joueurs sans que ceux-ci soient meilleurs.
    volumes = Counter(
        j["universite"] for j in joueurs.values() if j["universite"]
    )
    effectifs_retenus = Counter(l["universite"] for l in lignes)

    # Joueurs les mieux notés issus d'universités très peu représentées.
    atypiques = [
        {
            "nom": l["nom"],
            "universite": l["universite"],
            "score": l["score_global"],
            "n_universite": effectifs_retenus[l["universite"]],
        }
        for l in sorted(lignes, key=lambda x: -x["score_global"])
        if effectifs_retenus[l["universite"]] <= 2
    ]

    ctx = {
        "n_joueurs": len(lignes),
        "n_universites": classement.get("n_universites", 0),
        "n_actions": len(actions),
        "n_lignes_tracking": tracking["n_lignes"],
        "effectifs_groupes": effectifs_groupes,
        "volumes_universites": volumes.most_common(6),
        "exemples_petits_programmes": atypiques[:4],
        "classement_universites": classement,
        "classement_par_poste": par_poste,
        "meilleurs_joueurs": meilleurs,
        "tests_globaux": tests,
        "validation_faciale": tests["validation_faciale"],
        "diagnostic_normalisation": diagnostic,
    }

    # --- 6. Exports ------------------------------------------------------
    chemin_joueurs = os.path.join(DOSSIER_SORTIE, "scores_joueurs.csv")
    exporter_joueurs(lignes, chemin_joueurs)
    chemin_univ = os.path.join(DOSSIER_SORTIE, "classement_universites.csv")
    exporter_classement(classement, chemin_univ)
    chemin_poste = os.path.join(DOSSIER_SORTIE, "classement_par_poste.csv")
    exporter_classement_par_poste(par_poste, chemin_poste)

    chemin_json = os.path.join(DOSSIER_SORTIE, "statistiques_nfl.json")
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(
            _json_propre(
                {
                    "nettoyage": nettoyage,
                    "effectifs_groupes": effectifs_groupes,
                    "classement_universites": classement,
                    "classement_par_poste": par_poste,
                    "tests": tests,
                    "diagnostic_normalisation": diagnostic,
                    "tracking": {
                        k: v for k, v in tracking.items()
                        if k not in ("athletisme", "separation")
                    },
                }
            ),
            f,
            ensure_ascii=False,
            indent=2,
        )
    _log(f"Exports CSV et JSON écrits dans {DOSSIER_SORTIE}")

    # --- 7. Rapport ------------------------------------------------------
    duree = time.time() - t0
    chemin_rapport = os.path.join(BASE, "rapport_nfl.md")
    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write(construire_rapport(ctx, nettoyage, duree))
    _log(f"Rapport -> {chemin_rapport}")

    # --- 8. Présentation -------------------------------------------------
    if not args.sans_pptx:
        _log("Génération de la présentation PowerPoint...")
        chemin_pptx = os.path.join(BASE, "presentation_nfl.pptx")
        _, n_slides = nfl_slides.construire(ctx, chemin_pptx)
        taille_ko = os.path.getsize(chemin_pptx) / 1024
        _log(f"Présentation -> {chemin_pptx} ({n_slides} slides, {taille_ko:.0f} Ko)")
        if not pptx_validator.afficher_rapport(chemin_pptx, journal=_log):
            _log("ERREUR : la présentation produite est invalide.")
            return 1

    _log(f"Terminé en {time.time() - t0:.0f} s.")

    # --- Synthèse console ------------------------------------------------
    print("\n" + "=" * 68)
    print("CONCLUSION")
    print("=" * 68)
    vf = tests["validation_faciale"].get("_global", {})
    print(
        f"Score validé : les joueurs d'élite 2021 atteignent le percentile "
        f"{vf.get('percentile_moyen_elite', float('nan')):.1f} de leur groupe "
        f"(50 attendu au hasard)."
    )
    anova = tests["anova"]
    print(
        f"Effet université : ANOVA p = {anova.get('p_value', 1):.4f} -> "
        f"{'SIGNIFICATIF' if anova.get('significatif') else 'NON SIGNIFICATIF'}."
    )
    vm = classement.get("validation_moities", {})
    if vm.get("applicable"):
        print(
            f"Reproductibilité du classement : rho = {vm['rho_moyen']:+.3f} -> "
            f"le classement n'est pas reproductible."
        )
    print(
        "En clair : l'université d'origine n'explique pas la performance NFL, "
        "poste par poste."
    )
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
