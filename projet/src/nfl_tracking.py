"""
Passe de lecture du tracking Next Gen Stats (8,3 M lignes, Python pur).

Deux familles d'indicateurs sont extraites en un seul balayage :

1. ATHLÉTISME (toutes les frames, tous les joueurs)
   Vitesse de pointe et accélération de pointe atteintes sur les 8 semaines.
   Disponible pour tous les postes, donc comparable universellement.

2. SÉPARATION AU LÂCHER (une seule frame par action)
   À l'instant où le quarterback lâche le ballon (`pass_forward`), on mesure
   pour chaque receveur en route la distance au défenseur en couverture le
   plus proche, et réciproquement pour chaque défenseur en couverture.

   C'est l'indicateur qui permet d'évaluer les receveurs et les défenseurs de
   couverture, que les données PFF ne notent pas directement : PFF ne fournit
   la production qu'en pass rush et en protection.

Le fichier tracking n'a aucun champ entre guillemets et ne contient que des
valeurs numériques ou des libellés sans virgule : un `split(",")` direct est
sûr et nettement plus rapide que le module csv.
"""

from __future__ import annotations

import math
import os
import time
from collections import defaultdict

# Indices de colonnes du tracking :
# gameId,playId,nflId,frameId,time,jerseyNumber,team,playDirection,
# x,y,s,a,dis,o,dir,event
I_GAME, I_PLAY, I_NFL, I_FRAME = 0, 1, 2, 3
I_X, I_Y, I_S, I_A = 8, 9, 10, 11
I_EVENT = 15

# Événements marquant le lâcher du ballon, par ordre de préférence.
# `pass_forward` est l'annotation humaine (présente sur ~90 % des actions) ;
# `autoevent_passforward` est l'annotation automatique, prise en repli.
EVENEMENTS_LACHER = ("pass_forward", "autoevent_passforward", "qb_sack")


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def analyser_fichier(
    chemin: str,
    roles_par_action: dict[tuple[str, str], dict[str, str]],
    athletisme: dict[str, dict],
    separation: dict[str, dict],
) -> int:
    """Traite un fichier tracking d'un match. Met à jour les accumulateurs.

    Retourne le nombre de lignes lues.
    """
    # Tampon : (playId, frameId) -> [(nflId, x, y), ...]
    positions: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    # playId -> frameId du lâcher, selon la priorité des événements.
    frame_lacher: dict[str, tuple[int, str]] = {}
    game_id = None
    n_lignes = 0

    with open(chemin, "r", encoding="utf-8") as f:
        f.readline()  # en-tête
        for ligne in f:
            champs = ligne.rstrip("\n").split(",")
            if len(champs) <= I_EVENT:
                continue
            n_lignes += 1

            nfl_id = champs[I_NFL]
            if not nfl_id or nfl_id == "NA":
                continue  # ligne du ballon

            if game_id is None:
                game_id = champs[I_GAME]

            # --- 1. Athlétisme : pointes de vitesse et d'accélération -----
            a = athletisme.get(nfl_id)
            if a is None:
                a = athletisme[nfl_id] = {
                    "vitesse_max": 0.0,
                    "accel_max": 0.0,
                    "frames": 0,
                }
            try:
                vitesse = float(champs[I_S])
                accel = float(champs[I_A])
            except ValueError:
                vitesse = accel = 0.0
            if vitesse > a["vitesse_max"]:
                a["vitesse_max"] = vitesse
            if accel > a["accel_max"]:
                a["accel_max"] = accel
            a["frames"] += 1

            # --- 2. Tampon des positions pour la frame du lâcher ----------
            play_id = champs[I_PLAY]
            frame_id = champs[I_FRAME]
            positions[(play_id, frame_id)].append((nfl_id, champs[I_X], champs[I_Y]))

            evenement = champs[I_EVENT]
            if evenement in EVENEMENTS_LACHER:
                priorite = EVENEMENTS_LACHER.index(evenement)
                courant = frame_lacher.get(play_id)
                if courant is None or priorite < courant[0]:
                    frame_lacher[play_id] = (priorite, frame_id)

    if game_id is None:
        return n_lignes

    # --- 3. Séparation à l'instant du lâcher ------------------------------
    for play_id, (_, frame_id) in frame_lacher.items():
        lignes = positions.get((play_id, frame_id))
        if not lignes:
            continue
        roles = roles_par_action.get((game_id, play_id))
        if not roles:
            continue

        receveurs, couvreurs = [], []
        for nfl_id, sx, sy in lignes:
            role = roles.get(nfl_id)
            if role is None:
                continue
            try:
                x, y = float(sx), float(sy)
            except ValueError:
                continue
            if role == "Pass Route":
                receveurs.append((nfl_id, x, y))
            elif role == "Coverage":
                couvreurs.append((nfl_id, x, y))

        if not receveurs or not couvreurs:
            continue

        # Pour chaque receveur : distance au couvreur le plus proche.
        for nfl_id, x, y in receveurs:
            d = min(_distance(x, y, cx, cy) for _, cx, cy in couvreurs)
            _cumuler(separation, nfl_id, d)

        # Pour chaque couvreur : distance au receveur le plus proche.
        for nfl_id, x, y in couvreurs:
            d = min(_distance(x, y, rx, ry) for _, rx, ry in receveurs)
            _cumuler(separation, nfl_id, d)

    return n_lignes


def _cumuler(separation: dict[str, dict], nfl_id: str, distance: float) -> None:
    s = separation.get(nfl_id)
    if s is None:
        s = separation[nfl_id] = {"somme": 0.0, "n": 0, "distances": []}
    s["somme"] += distance
    s["n"] += 1
    # On conserve les distances pour pouvoir calculer une médiane, plus robuste
    # aux actions aberrantes (receveur oublié en zone, QB qui s'échappe).
    s["distances"].append(distance)


def analyser_tous(
    dossier_tracking: str,
    roles_par_action: dict[tuple[str, str], dict[str, str]],
    journal=print,
    limite_fichiers: int | None = None,
) -> dict:
    """Balaye tous les fichiers tracking et agrège les indicateurs par joueur."""
    fichiers = sorted(
        f for f in os.listdir(dossier_tracking)
        if f.startswith("tracking_") and f.endswith(".csv")
    )
    if limite_fichiers:
        fichiers = fichiers[:limite_fichiers]

    athletisme: dict[str, dict] = {}
    separation: dict[str, dict] = {}
    total_lignes = 0
    t0 = time.time()

    for i, nom in enumerate(fichiers, 1):
        total_lignes += analyser_fichier(
            os.path.join(dossier_tracking, nom),
            roles_par_action,
            athletisme,
            separation,
        )
        if i % 20 == 0 or i == len(fichiers):
            journal(
                f"  tracking {i}/{len(fichiers)} fichiers — "
                f"{total_lignes:,} lignes — {time.time() - t0:.0f} s"
            )

    # Consolidation des séparations.
    from . import nfl_stats as st

    resultat_separation = {}
    for nfl_id, s in separation.items():
        if s["n"] == 0:
            continue
        resultat_separation[nfl_id] = {
            "separation_moyenne": s["somme"] / s["n"],
            "separation_mediane": st.mediane(s["distances"]),
            "n_actions": s["n"],
        }

    return {
        "athletisme": athletisme,
        "separation": resultat_separation,
        "n_fichiers": len(fichiers),
        "n_lignes": total_lignes,
        "duree_s": time.time() - t0,
    }
