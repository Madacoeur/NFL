"""
Composition de la présentation PowerPoint « Performance NFL par poste et par
université ».

Toutes les diapositives sont construites avec des formes natives PowerPoint
(rectangles, traits, zones de texte) plutôt que des images : le résultat reste
net à tout niveau de zoom et chaque élément demeure éditable dans PowerPoint.
C'est aussi la seule option praticable ici, matplotlib étant indisponible.
"""

from __future__ import annotations

from .pptx_builder import Fragment, Paragraphe, Presentation, Slide
from . import nfl_data

# ---------------------------------------------------------------------------
# Système graphique
# ---------------------------------------------------------------------------

MARINE = "0B1F33"
MARINE_CLAIR = "16395C"
BLEU = "1B5E8C"
BLEU_PALE = "D8E4EE"
ROUGE = "D64550"
AMBRE = "E8A33D"
VERT = "2E9E8F"
VIOLET = "7D5BA6"
GRIS = "98A2AD"
GRIS_CLAIR = "E8ECF0"
FOND_CLAIR = "F2F5F8"
BLANC = "FFFFFF"
TEXTE = "1A2733"
TEXTE_DOUX = "5A6B7B"

TITRE_POLICE = "Calibri Light"
CORPS_POLICE = "Calibri"

# Géométrie (EMU). Diapositive 16:9 : 12 192 000 x 6 858 000.
LARGEUR = 12192000
HAUTEUR = 6858000
MARGE = 620000
CONTENU_L = LARGEUR - 2 * MARGE

Y_SURTITRE = 360000
Y_TITRE = 600000
Y_CONTENU = 1560000
Y_PIED = 6330000

COULEURS_GROUPES = {
    "Pass Rush": ROUGE,
    "Pass Block": BLEU,
    "Coverage": VERT,
    "Pass Route": AMBRE,
    "Pass": VIOLET,
}


# ---------------------------------------------------------------------------
# Briques réutilisables
# ---------------------------------------------------------------------------


def _fond(slide: Slide, couleur: str = BLANC) -> None:
    slide.rectangle(0, 0, LARGEUR, HAUTEUR, couleur=couleur)


def en_tete(
    slide: Slide,
    titre: str,
    surtitre: str = "",
    couleur_accent: str = BLEU,
    fond: str = BLANC,
) -> None:
    """Bandeau de titre standard des diapositives de contenu."""
    _fond(slide, fond)
    # Filet d'accent vertical à gauche du titre.
    slide.rectangle(MARGE, Y_SURTITRE, 62000, 780000, couleur=couleur_accent)
    if surtitre:
        slide.texte(
            surtitre.upper(),
            MARGE + 200000,
            Y_SURTITRE,
            CONTENU_L - 200000,
            260000,
            taille=11,
            gras=True,
            couleur=couleur_accent,
            police=CORPS_POLICE,
            espacement=160,
        )
    slide.texte(
        titre,
        MARGE + 200000,
        Y_TITRE,
        CONTENU_L - 200000,
        620000,
        taille=27,
        gras=True,
        couleur=MARINE,
        police=TITRE_POLICE,
    )


def pied(slide: Slide, texte: str = "", numero: int | None = None) -> None:
    """Pied de page : source à gauche, numéro à droite."""
    slide.ligne(MARGE, Y_PIED - 60000, LARGEUR - MARGE, Y_PIED - 60000, GRIS_CLAIR, 9525)
    if texte:
        slide.texte(
            texte,
            MARGE,
            Y_PIED,
            CONTENU_L - 600000,
            280000,
            taille=9,
            couleur=TEXTE_DOUX,
            police=CORPS_POLICE,
        )
    if numero is not None:
        slide.texte(
            str(numero),
            LARGEUR - MARGE - 500000,
            Y_PIED,
            500000,
            280000,
            taille=9,
            couleur=GRIS,
            police=CORPS_POLICE,
            alignement="droite",
        )


def cartes_kpi(
    slide: Slide,
    cartes: list[tuple[str, str, str]],
    x: int,
    y: int,
    largeur_totale: int,
    hauteur: int = 1150000,
    couleur: str = BLEU,
) -> None:
    """Rangée de cartes « chiffre clé ».

    `cartes` : liste de (valeur, libellé, note).
    """
    n = len(cartes)
    if n == 0:
        return
    ecart = 150000
    largeur = (largeur_totale - ecart * (n - 1)) // n
    for i, (valeur, libelle, note) in enumerate(cartes):
        cx = x + i * (largeur + ecart)
        slide.rectangle(cx, y, largeur, hauteur, couleur=FOND_CLAIR)
        slide.rectangle(cx, y, largeur, 46000, couleur=couleur)
        slide.texte(
            valeur,
            cx + 130000,
            y + 150000,
            largeur - 260000,
            480000,
            taille=29,
            gras=True,
            couleur=MARINE,
            police=TITRE_POLICE,
        )
        slide.texte(
            libelle,
            cx + 130000,
            y + 620000,
            largeur - 260000,
            250000,
            taille=11.5,
            gras=True,
            couleur=TEXTE,
            police=CORPS_POLICE,
        )
        if note:
            slide.texte(
                note,
                cx + 130000,
                y + 850000,
                largeur - 260000,
                250000,
                taille=9.5,
                couleur=TEXTE_DOUX,
                police=CORPS_POLICE,
            )


def largeur_piste_barres(
    largeur: int,
    largeur_libelle: int,
    largeur_valeur: int = 700000,
    largeur_annotation: int = 1000000,
    avec_annotation: bool = True,
) -> int:
    """Largeur de la piste d'un diagramme `barres`, pour positionner un repère.

    Centralise le calcul afin que les repères tracés par les appelants
    (ligne de référence, graduations) restent alignés sur les barres même si
    les marges internes changent.
    """
    reserve = largeur_annotation if avec_annotation else 0
    return largeur - largeur_libelle - largeur_valeur - reserve - 160000


def barres(
    slide: Slide,
    donnees: list[tuple[str, float, str]],
    x: int,
    y: int,
    largeur: int,
    hauteur_ligne: int = 330000,
    largeur_libelle: int = 2500000,
    largeur_valeur: int = 700000,
    maximum: float | None = None,
    minimum: float = 0.0,
    couleur: str = BLEU,
    couleur_premiere: str | None = None,
    taille_libelle: float = 11.5,
    format_valeur: str = "{:.1f}",
    largeur_annotation: int = 1000000,
) -> None:
    """Diagramme à barres horizontales.

    `donnees` : liste de (libellé, valeur, annotation). L'annotation est
    affichée en gris à droite de la valeur (effectif, p-value, etc.).

    Budget horizontal : libellé + piste + valeur + annotation doivent tenir
    dans `largeur`. L'espace de l'annotation n'est réservé que si au moins une
    annotation est non vide, sinon la piste occupe la place disponible.
    """
    if not donnees:
        return
    valeurs = [v for _, v, _ in donnees]
    haut = maximum if maximum is not None else max(valeurs)
    bas = minimum
    etendue = (haut - bas) or 1.0

    avec_annotation = any(a for _, _, a in donnees)
    reserve_annotation = largeur_annotation if avec_annotation else 0
    largeur_piste = largeur_piste_barres(
        largeur, largeur_libelle, largeur_valeur, largeur_annotation, avec_annotation
    )
    if largeur_piste <= 0:
        raise ValueError(
            f"barres() : largeur insuffisante ({largeur}) pour libellé "
            f"{largeur_libelle} + valeur {largeur_valeur} + annotation "
            f"{reserve_annotation}"
        )

    for i, (libelle, valeur, annotation) in enumerate(donnees):
        ly = y + i * hauteur_ligne
        hauteur_barre = int(hauteur_ligne * 0.56)
        decalage = (hauteur_ligne - hauteur_barre) // 2

        slide.texte(
            libelle,
            x,
            ly + decalage - 28000,
            largeur_libelle - 80000,
            hauteur_barre + 56000,
            taille=taille_libelle,
            couleur=TEXTE,
            police=CORPS_POLICE,
            ancrage="milieu",
        )

        # Piste de fond, puis barre proportionnelle.
        px = x + largeur_libelle
        slide.rectangle(px, ly + decalage, largeur_piste, hauteur_barre, couleur=GRIS_CLAIR)
        part = max(0.0, min(1.0, (valeur - bas) / etendue))
        largeur_barre = max(int(largeur_piste * part), 8000)
        teinte = couleur_premiere if (i == 0 and couleur_premiere) else couleur
        slide.rectangle(px, ly + decalage, largeur_barre, hauteur_barre, couleur=teinte)

        slide.texte(
            format_valeur.format(valeur),
            px + largeur_piste + 90000,
            ly + decalage - 28000,
            largeur_valeur,
            hauteur_barre + 56000,
            taille=taille_libelle,
            gras=True,
            couleur=MARINE,
            police=CORPS_POLICE,
            ancrage="milieu",
        )
        if annotation and reserve_annotation:
            slide.texte(
                annotation,
                px + largeur_piste + 90000 + largeur_valeur,
                ly + decalage - 28000,
                reserve_annotation - 90000,
                hauteur_barre + 56000,
                taille=9.5,
                couleur=TEXTE_DOUX,
                police=CORPS_POLICE,
                ancrage="milieu",
            )


def tableau(
    slide: Slide,
    entetes: list[str],
    lignes: list[list[str]],
    x: int,
    y: int,
    largeurs: list[int],
    hauteur_ligne: int = 330000,
    couleur_entete: str = MARINE,
    taille: float = 11,
    alignements: list[str] | None = None,
    surlignage: list[int] | None = None,
) -> None:
    """Tableau simple à base de rectangles et de zones de texte."""
    largeur_totale = sum(largeurs)
    alignements = alignements or ["gauche"] * len(entetes)
    surlignage = surlignage or []

    # En-tête.
    slide.rectangle(x, y, largeur_totale, hauteur_ligne, couleur=couleur_entete)
    cx = x
    for i, titre in enumerate(entetes):
        slide.texte(
            titre,
            cx + 90000,
            y,
            largeurs[i] - 180000,
            hauteur_ligne,
            taille=taille - 0.5,
            gras=True,
            couleur=BLANC,
            police=CORPS_POLICE,
            alignement=alignements[i],
            ancrage="milieu",
        )
        cx += largeurs[i]

    # Corps.
    for j, ligne in enumerate(lignes):
        ly = y + (j + 1) * hauteur_ligne
        if j in surlignage:
            fond = BLEU_PALE
        else:
            fond = FOND_CLAIR if j % 2 == 0 else BLANC
        slide.rectangle(x, ly, largeur_totale, hauteur_ligne, couleur=fond)
        cx = x
        for i, cellule in enumerate(ligne):
            if i >= len(largeurs):
                break
            slide.texte(
                str(cellule),
                cx + 90000,
                ly,
                largeurs[i] - 180000,
                hauteur_ligne,
                taille=taille,
                gras=(i == 0),
                couleur=TEXTE,
                police=CORPS_POLICE,
                alignement=alignements[i],
                ancrage="milieu",
            )
            cx += largeurs[i]

    slide.ligne(
        x,
        y + (len(lignes) + 1) * hauteur_ligne,
        x + largeur_totale,
        y + (len(lignes) + 1) * hauteur_ligne,
        GRIS_CLAIR,
        9525,
    )


def encadre(
    slide: Slide,
    titre: str,
    corps: str,
    x: int,
    y: int,
    largeur: int,
    hauteur: int,
    couleur: str = AMBRE,
    fond: str = FOND_CLAIR,
) -> None:
    """Encadré de mise en avant (constat, avertissement, conclusion)."""
    slide.rectangle(x, y, largeur, hauteur, couleur=fond)
    slide.rectangle(x, y, 52000, hauteur, couleur=couleur)
    slide.texte(
        titre,
        x + 200000,
        y + 110000,
        largeur - 380000,
        300000,
        taille=12.5,
        gras=True,
        couleur=couleur,
        police=CORPS_POLICE,
    )
    slide.texte(
        corps,
        x + 200000,
        y + 420000,
        largeur - 380000,
        hauteur - 520000,
        taille=12,
        couleur=TEXTE,
        police=CORPS_POLICE,
        interligne=1.25,
    )


def puces(
    slide: Slide,
    elements: list[tuple[str, str]],
    x: int,
    y: int,
    largeur: int,
    hauteur: int,
    taille: float = 13,
) -> None:
    """Liste à puces où chaque item est (amorce en gras, suite)."""
    paras = []
    for gras, suite in elements:
        frags = []
        if gras:
            frags.append(Fragment(gras, taille=taille, gras=True, couleur=MARINE,
                                  police=CORPS_POLICE))
        if suite:
            frags.append(Fragment(suite, taille=taille, couleur=TEXTE,
                                  police=CORPS_POLICE))
        paras.append(
            Paragraphe(frags, puce=True, espace_apres=600, interligne=1.2)
        )
    slide.bloc_texte(paras, x, y, largeur, hauteur)


# ---------------------------------------------------------------------------
# Formatage
# ---------------------------------------------------------------------------


def _p(valeur) -> str:
    """Formate une p-value."""
    if valeur is None or valeur != valeur:
        return "n/d"
    if valeur < 0.001:
        return "p < 0,001"
    return f"p = {valeur:.3f}".replace(".", ",")


def _nb(valeur, decimales: int = 1) -> str:
    """Formate un nombre à la française."""
    if valeur is None or valeur != valeur:
        return "n/d"
    return f"{valeur:.{decimales}f}".replace(".", ",")


def _tronquer(texte: str, maxi: int) -> str:
    return texte if len(texte) <= maxi else texte[: maxi - 1] + "…"


# ---------------------------------------------------------------------------
# Diapositives
# ---------------------------------------------------------------------------


def slide_couverture(pres: Presentation, ctx: dict) -> None:
    s = pres.ajouter_slide()
    _fond(s, MARINE)
    # Bandes d'accent décoratives en bas.
    for i, c in enumerate([ROUGE, AMBRE, VERT, BLEU, VIOLET]):
        s.rectangle(0 + i * (LARGEUR // 5), HAUTEUR - 110000, LARGEUR // 5, 110000,
                    couleur=c)

    s.texte(
        "ANALYSE DE DONNÉES SPORTIVES · NFL 2021",
        MARGE,
        1180000,
        CONTENU_L,
        300000,
        taille=12,
        gras=True,
        couleur=AMBRE,
        police=CORPS_POLICE,
        espacement=200,
    )
    s.texte(
        "Quelles universités produisent\nles joueurs les plus performants ?",
        MARGE,
        1620000,
        CONTENU_L,
        1700000,
        taille=42,
        gras=True,
        couleur=BLANC,
        police=TITRE_POLICE,
        interligne=1.1,
    )
    s.rectangle(MARGE, 3500000, 1500000, 46000, couleur=ROUGE)
    s.texte(
        "Une mesure de la performance poste par poste, confrontée à "
        "l'université d'origine",
        MARGE,
        3700000,
        CONTENU_L - 1000000,
        500000,
        taille=16,
        couleur="B9C7D4",
        police=CORPS_POLICE,
    )

    cartes = [
        (f"{ctx['n_joueurs']}", "joueurs analysés", "≥ 50 snaps joués"),
        (f"{ctx['n_universites']}", "universités classées", "≥ 5 joueurs"),
        ("8,3 M", "positions GPS", "tracking à 10 Hz"),
        (f"{ctx['n_actions']}", "actions de passe", "semaines 1 à 8"),
    ]
    # Cartes claires sur fond marine : le contraste reste lisible.
    cartes_kpi(s, cartes, MARGE, 4450000, CONTENU_L, hauteur=1050000, couleur=AMBRE)
    s.texte(
        "Données NFL Next Gen Stats + scouting Pro Football Focus · "
        "Big Data Bowl 2023",
        MARGE,
        5750000,
        CONTENU_L,
        300000,
        taille=10,
        couleur=GRIS,
        police=CORPS_POLICE,
    )


def slide_question(pres: Presentation, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(
        s,
        "Transposer une méthode éprouvée à un nouveau terrain",
        "point de départ",
        BLEU,
    )

    s.texte(
        "Le projet d'origine",
        MARGE,
        Y_CONTENU,
        5100000,
        330000,
        taille=14,
        gras=True,
        couleur=BLEU,
        police=CORPS_POLICE,
    )
    s.rectangle(MARGE, Y_CONTENU + 400000, 5100000, 1450000, couleur=FOND_CLAIR)
    s.texte(
        "« L'université de formation a-t-elle un effet sur la réussite "
        "professionnelle d'un diplômé, domaine par domaine ? »\n\n"
        "Score composite · percentile intra-domaine · ANOVA, Chi-2, régression",
        MARGE + 190000,
        Y_CONTENU + 540000,
        5100000 - 380000,
        1200000,
        taille=12,
        couleur=TEXTE,
        police=CORPS_POLICE,
        interligne=1.2,
    )

    s.texte(
        "La transposition à la NFL",
        MARGE + 5700000,
        Y_CONTENU,
        5100000,
        330000,
        taille=14,
        gras=True,
        couleur=ROUGE,
        police=CORPS_POLICE,
    )
    s.rectangle(MARGE + 5700000, Y_CONTENU + 400000, 5100000, 1450000, couleur="FBEDEE")
    s.texte(
        "« L'université d'origine a-t-elle un effet sur la performance d'un "
        "joueur NFL, poste par poste ? »\n\n"
        "Même ossature statistique · percentile intra-poste · "
        "données de terrain mesurées",
        MARGE + 5700000 + 190000,
        Y_CONTENU + 540000,
        5100000 - 380000,
        1200000,
        taille=12,
        couleur=TEXTE,
        police=CORPS_POLICE,
        interligne=1.2,
    )

    encadre(
        s,
        "Pourquoi ce terrain est plus solide que le précédent",
        "Le projet d'origine reposait sur des données synthétiques, avec une "
        "corrélation injectée volontairement pour tester la détection. Ici, les "
        "données sont réelles et mesurées : position GPS de chaque joueur dix "
        "fois par seconde, et notation manuelle de chaque action par des "
        "analystes professionnels. La conclusion, quelle qu'elle soit, porte "
        "donc sur le monde réel — et non sur un signal que l'on aurait "
        "soi-même introduit.",
        MARGE,
        Y_CONTENU + 2060000,
        CONTENU_L,
        1600000,
        couleur=AMBRE,
    )
    pied(s, "Dépôt NFL · projet « universités » transposé au Big Data Bowl 2023", numero)


def slide_donnees(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Quatre sources croisées, dont le tracking GPS", "les données", BLEU)

    cartes_kpi(
        s,
        [
            ("1 679", "joueurs référencés", "université, poste, physique"),
            ("188 254", "lignes de scouting", "notation PFF par action"),
            ("8 557", "actions de passe", "contexte et résultat"),
            ("8 314 178", "positions GPS", "22 joueurs + ballon, 10 Hz"),
        ],
        MARGE,
        Y_CONTENU,
        CONTENU_L,
        hauteur=1100000,
        couleur=BLEU,
    )

    tableau(
        s,
        ["Source", "Ce qu'on en tire", "Rôle dans le score"],
        [
            ["players.csv", "Université, poste officiel, taille, poids",
             "Clé de rattachement université ↔ joueur"],
            ["pffScoutingData.csv", "Rôle tenu, sacks, hits, hurries, pressions "
             "concédées", "Production en pass rush et en protection"],
            ["tracking/*.csv", "Vitesse et accélération de pointe, position de "
             "chaque joueur au lâcher", "Athlétisme + séparation receveur/défenseur"],
            ["plays.csv", "Résultat de l'action, couverture, formation",
             "Efficacité des quarterbacks"],
        ],
        MARGE,
        Y_CONTENU + 1340000,
        [2500000, 4400000, CONTENU_L - 6900000],
        hauteur_ligne=390000,
        taille=11,
    )

    encadre(
        s,
        "L'apport décisif : mesurer ce que le scouting ne note pas",
        "Les données PFF ne notent la production que des pass rushers et des "
        "bloqueurs. Receveurs et défenseurs de couverture n'ont aucune "
        "statistique de réussite. On la reconstruit depuis le tracking : à "
        "l'instant exact où le quarterback lâche le ballon, on calcule la "
        "distance entre chaque receveur et le défenseur le plus proche. Cela "
        "rend les 541 receveurs et défenseurs de couverture évaluables.",
        MARGE,
        Y_CONTENU + 3200000,
        CONTENU_L,
        1300000,
        couleur=VERT,
    )
    pied(s, "NFL Next Gen Stats · Pro Football Focus · saison 2021, semaines 1 à 8", numero)


def slide_methode(pres: Presentation, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Un score de performance en trois composantes", "méthode", BLEU)

    # Schéma de pondération.
    composantes = [
        ("Production", 50, ROUGE, "Indicateur propre au poste"),
        ("Athlétisme", 25, AMBRE, "Vitesse et accélération de pointe"),
        ("Temps de jeu", 25, VERT, "Nombre de snaps joués"),
    ]
    y = Y_CONTENU
    x_barre = MARGE + 2300000
    largeur_max = 5000000
    for i, (nom, poids, couleur, note) in enumerate(composantes):
        ly = y + i * 560000
        s.texte(nom, MARGE, ly + 40000, 2200000, 350000, taille=14, gras=True,
                couleur=MARINE, police=CORPS_POLICE, ancrage="milieu")
        s.rectangle(x_barre, ly + 60000, int(largeur_max * poids / 50), 300000,
                    couleur=couleur)
        s.texte(f"{poids} %", x_barre + int(largeur_max * poids / 50) + 120000,
                ly + 40000, 700000, 350000, taille=13, gras=True, couleur=couleur,
                police=CORPS_POLICE, ancrage="milieu")
        s.texte(note, x_barre + largeur_max + 900000, ly + 40000,
                CONTENU_L - largeur_max - 3200000, 350000, taille=11,
                couleur=TEXTE_DOUX, police=CORPS_POLICE, ancrage="milieu")

    encadre(
        s,
        "La précaution centrale : noter chacun contre ses pairs",
        "Chaque composante est convertie en percentile à l'intérieur de la "
        "famille de postes du joueur, jamais sur l'ensemble des joueurs. Un "
        "running back qui sort du backfield obtient mécaniquement 5,6 yards de "
        "séparation là où un wide receiver affronte un cornerback à 2,5 yards : "
        "les noter sur la même échelle conduirait à conclure que les running "
        "backs sont les meilleurs receveurs de la ligue. On compare donc les WR "
        "aux WR, les tackles aux tackles, les cornerbacks aux cornerbacks.",
        MARGE,
        Y_CONTENU + 1900000,
        CONTENU_L,
        1450000,
        couleur=BLEU,
    )

    puces(
        s,
        [
            ("Pourquoi le temps de jeu compte — ",
             "un entraîneur fait jouer ses meilleurs joueurs ; le volume de "
             "snaps est un jugement de qualité émis par le staff."),
            ("Pourquoi l'athlétisme ne pèse que 25 % — ",
             "la vitesse de pointe est une aptitude, pas un résultat ; elle "
             "éclaire le potentiel sans se substituer à la production."),
        ],
        MARGE,
        Y_CONTENU + 3500000,
        CONTENU_L,
        1000000,
        taille=12.5,
    )
    pied(s, "Score sur 0-100 · percentile calculé par famille de postes", numero)


def slide_indicateurs(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Ce que « performer » veut dire à chaque poste", "méthode", BLEU)

    lignes = []
    for role in nfl_data.ORDRE_GROUPES:
        info = ctx["effectifs_groupes"].get(role)
        if not info:
            continue
        lignes.append([
            nfl_data.GROUPES[role],
            info["postes"],
            nfl_data.LIBELLE_PRODUCTION[role],
            "plus haut" if nfl_data.SENS_PRODUCTION[role] else "plus bas",
            str(info["n"]),
        ])

    tableau(
        s,
        ["Groupe", "Postes concernés", "Indicateur de production",
         "Sens favorable", "Joueurs"],
        lignes,
        MARGE,
        Y_CONTENU,
        [1900000, 2500000, 3500000, 1550000, CONTENU_L - 9450000],
        hauteur_ligne=400000,
        taille=11.5,
        alignements=["gauche", "gauche", "gauche", "centre", "centre"],
    )

    encadre(
        s,
        "Le rôle réellement tenu sur le terrain, pas l'étiquette du poste",
        "Le groupe d'un joueur n'est pas déduit de son poste officiel mais du "
        "rôle que PFF lui attribue majoritairement sur ses snaps. C'est "
        "nécessaire : les 136 outside linebackers du jeu de données se "
        "scindent naturellement en 82 pass rushers et 54 défenseurs de "
        "couverture selon le schéma de leur équipe. Les classer sur leur seule "
        "étiquette « OLB » mélangerait deux métiers distincts.",
        MARGE,
        Y_CONTENU + 2550000,
        CONTENU_L,
        1350000,
        couleur=VIOLET,
    )
    pied(s, "Rôles PFF : Pass Rush, Pass Block, Coverage, Pass Route, Pass", numero)


def slide_validation(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(
        s,
        "Le score retrouve-t-il les joueurs d'élite ? Oui",
        "validation",
        VERT,
    )

    vf = ctx["validation_faciale"]
    donnees = []
    for role in nfl_data.ORDRE_GROUPES:
        r = vf.get(role)
        if not r:
            continue
        donnees.append((
            r["groupe"],
            r["percentile_moyen"],
            f"{r['n_elite_trouves']}/{r['n_elite_cherches']} joueurs",
        ))

    s.texte(
        "Percentile moyen des Pro Bowlers / All-Pro 2021 dans leur groupe",
        MARGE,
        Y_CONTENU,
        CONTENU_L,
        300000,
        taille=12.5,
        gras=True,
        couleur=MARINE,
        police=CORPS_POLICE,
    )
    barres(
        s,
        donnees,
        MARGE,
        Y_CONTENU + 420000,
        CONTENU_L - 300000,
        hauteur_ligne=400000,
        largeur_libelle=2100000,
        maximum=100.0,
        couleur=VERT,
        couleur_premiere=VERT,
        format_valeur="{:.0f}",
    )

    # Repère « hasard » : aligné sur la piste des barres via le calcul partagé.
    y_rep = Y_CONTENU + 420000
    hauteur_bloc = 400000 * max(len(donnees), 1)
    x_piste = MARGE + 2100000
    largeur_piste = largeur_piste_barres(
        CONTENU_L - 300000, 2100000, avec_annotation=bool(donnees)
    )
    x_50 = x_piste + largeur_piste // 2
    s.ligne(x_50, y_rep - 60000, x_50, y_rep + hauteur_bloc, ROUGE, 19050)
    s.texte(
        "50 = attendu si le score était du bruit",
        x_50 - 1400000,
        y_rep + hauteur_bloc + 40000,
        2800000,
        280000,
        taille=9.5,
        gras=True,
        couleur=ROUGE,
        police=CORPS_POLICE,
        alignement="centre",
    )

    global_ = vf.get("_global", {})
    encadre(
        s,
        "Un contrôle de validité externe, indépendant des données",
        f"Les 30 joueurs sélectionnés en Pro Bowl ou All-Pro en 2021 atteignent "
        f"un percentile moyen de {_nb(global_.get('percentile_moyen_elite'))} "
        f"dans leur groupe, là où un score sans valeur les aurait placés autour "
        f"de 50. En pass rush, les huit joueurs d'élite recherchés sont tous "
        f"dans le tiers supérieur. Le score mesure donc bien la performance — "
        f"ce qui autorise à l'utiliser pour juger les universités.",
        MARGE,
        Y_CONTENU + 2750000,
        CONTENU_L,
        1300000,
        couleur=VERT,
    )
    pied(s, "Référence externe : sélections Pro Bowl et All-Pro de la saison 2021", numero)


def slide_groupe(pres: Presentation, role: str, ctx: dict, numero: int) -> None:
    """Une diapositive par groupe de postes : meilleurs joueurs + universités."""
    s = pres.ajouter_slide()
    couleur = COULEURS_GROUPES.get(role, BLEU)
    libelle = nfl_data.GROUPES.get(role, role)
    en_tete(
        s,
        f"{libelle} — les joueurs et les universités qui ressortent",
        f"poste · {libelle}",
        couleur,
    )

    # --- Meilleurs joueurs -------------------------------------------
    joueurs = ctx["meilleurs_joueurs"].get(role, [])[:6]
    s.texte(
        f"Top 6 joueurs · {nfl_data.LIBELLE_PRODUCTION.get(role, '')}",
        MARGE,
        Y_CONTENU,
        6000000,
        290000,
        taille=12.5,
        gras=True,
        couleur=MARINE,
        police=CORPS_POLICE,
    )
    donnees_joueurs = [
        (
            f"{_tronquer(j['nom'], 20)}  ·  {_tronquer(j['universite'], 18)}",
            j["score_global"],
            f"{j['poste']}",
        )
        for j in joueurs
    ]
    barres(
        s,
        donnees_joueurs,
        MARGE,
        Y_CONTENU + 380000,
        CONTENU_L,
        hauteur_ligne=345000,
        largeur_libelle=4300000,
        maximum=100.0,
        couleur=couleur,
        format_valeur="{:.0f}",
    )

    # --- Classement des universités ----------------------------------
    y_univ = Y_CONTENU + 380000 + 345000 * max(len(donnees_joueurs), 1) + 300000
    resultat = ctx["classement_par_poste"].get(role, {})

    if resultat.get("applicable"):
        classement = resultat["classement"][:5]
        signal = resultat.get("signal_detectable", True)
        s.texte(
            "Top 5 universités · score brut"
            + (
                " — le score régularisé, lui, ne les distingue plus"
                if not signal
                else " et score régularisé"
            ),
            MARGE,
            y_univ,
            6700000,
            290000,
            taille=12.5,
            gras=True,
            couleur=MARINE,
            police=CORPS_POLICE,
        )
        # Quand aucun signal inter-universités n'est détectable, le score
        # régularisé est plat par construction : afficher cinq barres
        # identiques n'apprendrait rien. On montre alors le score brut — ce
        # qu'un classement naïf retiendrait — et on rappelle en annotation la
        # valeur régularisée, pour rendre l'écrasement visible.
        if signal:
            donnees_univ = [
                (
                    _tronquer(c["universite"], 24),
                    c["score_regularise"],
                    f"n={c['n_joueurs']} · brut {_nb(c['score_brut'], 0)}",
                )
                for c in classement
            ]
        else:
            donnees_univ = [
                (
                    _tronquer(c["universite"], 24),
                    c["score_brut"],
                    f"n={c['n_joueurs']} → {_nb(c['score_regularise'], 0)}",
                )
                for c in classement
            ]
        barres(
            s,
            donnees_univ,
            MARGE,
            y_univ + 370000,
            6700000,
            hauteur_ligne=320000,
            largeur_libelle=2350000,
            largeur_valeur=620000,
            maximum=100.0,
            couleur=GRIS,
            format_valeur="{:.0f}",
        )

        anova = resultat.get("anova", {})
        vm = resultat.get("validation_moities", {})
        statut = (
            "effet significatif"
            if anova.get("significatif")
            else "aucun effet significatif"
        )
        corps = (
            f"ANOVA entre les {resultat['n_universites_eligibles']} universités "
            f"éligibles : {_p(anova.get('p_value'))}. "
        )
        if vm.get("applicable"):
            corps += f"Validation par moitiés : ρ = {_nb(vm.get('rho_moyen'), 2)}. "
        if not signal:
            corps += (
                "La dispersion entre universités n'excède pas le bruit "
                "d'échantillonnage : après régularisation, tous les "
                "établissements convergent vers la même valeur. "
            )
        corps += (
            "Le classement ci-contre est donc indicatif, non concluant."
        )
        encadre(
            s,
            f"Lecture : {statut}",
            corps,
            MARGE + 7000000,
            y_univ + 240000,
            CONTENU_L - 7000000,
            1550000,
            couleur=couleur,
        )
    else:
        encadre(
            s,
            "Classement par université impossible à ce poste",
            f"Le groupe ne compte que {resultat.get('n_joueurs_groupe', 0)} "
            f"joueurs, et aucune université n'atteint le seuil de 3 joueurs "
            f"nécessaire pour calculer une moyenne interprétable. Publier un "
            f"classement ici reviendrait à comparer des établissements sur un "
            f"ou deux individus.",
            MARGE,
            y_univ,
            CONTENU_L,
            1300000,
            couleur=ROUGE,
        )

    pied(
        s,
        f"{resultat.get('n_joueurs_groupe', 0)} joueurs dans le groupe · "
        f"score 0-100, percentile intra-poste",
        numero,
    )


def slide_classement_general(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Le classement général, tous postes confondus", "résultats", BLEU)

    cl = ctx["classement_universites"]
    lignes = []
    for c in cl["classement"][:10]:
        postes = " · ".join(
            f"{k} {v}" for k, v in list(c["repartition_postes"].items())[:3]
        )
        lignes.append([
            str(c["rang"]),
            _tronquer(c["universite"], 22),
            str(c["n_joueurs"]),
            _nb(c["score_brut"]),
            _nb(c["score_regularise"]),
            _p(c["p_value_vs_reste"]),
            _tronquer(postes, 34),
        ])

    tableau(
        s,
        ["#", "Université", "Joueurs", "Score brut", "Score régularisé",
         "Significativité", "Répartition par poste"],
        lignes,
        MARGE,
        Y_CONTENU,
        [420000, 2450000, 900000, 1150000, 1550000, 1450000,
         CONTENU_L - 7920000],
        hauteur_ligne=330000,
        taille=10.5,
        alignements=["centre", "gauche", "centre", "centre", "centre",
                     "centre", "gauche"],
    )

    encadre(
        s,
        "Lire l'écart entre les deux colonnes de score",
        "Le score brut est la moyenne réelle des joueurs d'une université. Le "
        "score régularisé corrige l'effet de taille d'échantillon : une "
        "moyenne calculée sur 6 joueurs est beaucoup moins fiable qu'une "
        "moyenne sur 34. Plus l'effectif est faible, plus le score est tiré "
        "vers la moyenne générale. L'écrasement des écarts après "
        "régularisation est en soi le résultat principal de cette analyse.",
        MARGE,
        Y_CONTENU + 3850000,
        CONTENU_L,
        1250000,
        couleur=AMBRE,
    )
    pied(
        s,
        f"{cl['n_universites']} universités avec 5 joueurs ou plus · "
        f"{cl['n_joueurs']} joueurs",
        numero,
    )


def slide_effet_reel(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Cet écart entre universités est-il réel ?", "test", ROUGE)

    tests = ctx["tests_globaux"]
    anova = tests["anova"]
    chi2 = tests["chi2"]

    lignes = [
        [
            "ANOVA",
            "Les moyennes diffèrent-elles entre universités ?",
            f"F = {_nb(anova.get('f_statistic'), 2)}",
            _p(anova.get("p_value")),
            "Non" if not anova.get("significatif") else "Oui",
        ],
        [
            "Chi-2",
            "Université et niveau de performance sont-ils liés ?",
            f"V = {_nb(chi2.get('cramer_v'), 3)}",
            _p(chi2.get("p_value")),
            "Non" if not chi2.get("significatif") else "Oui",
        ],
    ]
    for role in nfl_data.ORDRE_GROUPES:
        r = ctx["classement_par_poste"].get(role, {})
        if not r.get("applicable"):
            continue
        a = r["anova"]
        lignes.append([
            f"ANOVA · {r['groupe']}",
            f"Effet université dans le groupe « {r['groupe']} »",
            f"F = {_nb(a.get('f_statistic'), 2)}",
            _p(a.get("p_value")),
            "Non" if not a.get("significatif") else "Oui",
        ])

    tableau(
        s,
        ["Test", "Question posée", "Statistique", "p-value", "Effet détecté ?"],
        lignes,
        MARGE,
        Y_CONTENU,
        [2250000, 4350000, 1350000, 1450000, CONTENU_L - 9400000],
        hauteur_ligne=345000,
        taille=11,
        alignements=["gauche", "gauche", "centre", "centre", "centre"],
    )

    encadre(
        s,
        "Aucun test ne détecte d'effet université, à aucun poste",
        "Toutes les p-values dépassent largement le seuil de 0,05. Autrement "
        "dit : les écarts observés dans le classement précédent sont "
        "compatibles avec le simple hasard d'échantillonnage. Avec une médiane "
        "de 3 joueurs par université, il suffit qu'un établissement ait "
        "« tiré » deux bons joueurs pour grimper au classement sans qu'aucun "
        "effet de formation n'existe.",
        MARGE,
        Y_CONTENU + 345000 * (len(lignes) + 1) + 280000,
        CONTENU_L,
        1300000,
        couleur=ROUGE,
    )
    faibles = chi2.get("cellules_effectif_faible", 0)
    total_cellules = chi2.get("cellules_total", 0)
    note_chi2 = (
        f" · Chi-2 à interpréter avec prudence : {faibles} des "
        f"{total_cellules} cellules ont un effectif théorique inférieur à 5"
        if faibles
        else ""
    )
    pied(
        s,
        f"Seuil de significativité retenu : α = 0,05{note_chi2}",
        numero,
    )


def slide_split_half(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Le test décisif : le classement est-il reproductible ?",
            "test de robustesse", ROUGE)

    s.texte(
        "Principe — on coupe au hasard les joueurs de chaque université en deux "
        "moitiés, on classe les universités sur la première moitié, puis on "
        "vérifie si ce classement prédit celui de la seconde. Répété 200 fois.",
        MARGE,
        Y_CONTENU,
        CONTENU_L,
        620000,
        taille=12.5,
        couleur=TEXTE,
        police=CORPS_POLICE,
        interligne=1.25,
    )

    donnees = []
    vm_global = ctx["classement_universites"].get("validation_moities", {})
    if vm_global.get("applicable"):
        donnees.append(("Tous postes", vm_global["rho_moyen"], ""))
    for role in nfl_data.ORDRE_GROUPES:
        r = ctx["classement_par_poste"].get(role, {})
        vm = r.get("validation_moities", {})
        if r.get("applicable") and vm.get("applicable"):
            donnees.append((r["groupe"], vm["rho_moyen"], ""))

    s.texte(
        "Corrélation moyenne entre les deux moitiés (ρ de Spearman)",
        MARGE,
        Y_CONTENU + 760000,
        CONTENU_L,
        290000,
        taille=12.5,
        gras=True,
        couleur=MARINE,
        police=CORPS_POLICE,
    )

    # Échelle de -1 à +1 avec axe zéro marqué.
    x_piste = MARGE + 2200000
    largeur_piste = 6200000
    y0 = Y_CONTENU + 1130000
    hauteur_ligne = 350000

    for i, (libelle, rho, _) in enumerate(donnees):
        ly = y0 + i * hauteur_ligne
        s.texte(libelle, MARGE, ly, 2100000, hauteur_ligne, taille=11.5,
                couleur=TEXTE, police=CORPS_POLICE, ancrage="milieu")
        s.rectangle(x_piste, ly + 90000, largeur_piste, 170000, couleur=GRIS_CLAIR)
        centre = x_piste + largeur_piste // 2
        demi = largeur_piste // 2
        longueur = int(abs(rho) * demi)
        couleur_barre = VERT if rho > 0.3 else ROUGE
        if rho >= 0:
            s.rectangle(centre, ly + 90000, max(longueur, 6000), 170000,
                        couleur=couleur_barre)
        else:
            s.rectangle(centre - max(longueur, 6000), ly + 90000,
                        max(longueur, 6000), 170000, couleur=couleur_barre)
        s.texte(f"{rho:+.3f}".replace(".", ","),
                x_piste + largeur_piste + 130000, ly, 900000, hauteur_ligne,
                taille=11.5, gras=True, couleur=MARINE, police=CORPS_POLICE,
                ancrage="milieu")

    # Axe zéro et graduations.
    bas = y0 + hauteur_ligne * max(len(donnees), 1)
    centre = x_piste + largeur_piste // 2
    s.ligne(centre, y0 - 40000, centre, bas, MARINE, 19050)
    for pos, lab in [(0, "−1"), (0.25, "−0,5"), (0.5, "0"), (0.75, "+0,5"), (1, "+1")]:
        xg = x_piste + int(largeur_piste * pos)
        s.texte(lab, xg - 300000, bas + 30000, 600000, 260000, taille=9,
                couleur=TEXTE_DOUX, police=CORPS_POLICE, alignement="centre")
    s.texte("ρ ≈ 0 : le classement ne se reproduit pas d'une moitié à l'autre",
            x_piste, bas + 330000, largeur_piste, 280000, taille=10,
            gras=True, italique=True, couleur=ROUGE, police=CORPS_POLICE,
            alignement="centre")

    encadre(
        s,
        "Conclusion du test : le classement n'est pas reproductible",
        f"Une corrélation moyenne de "
        f"{_nb(vm_global.get('rho_moyen'), 3) if vm_global.get('applicable') else 'n/d'} "
        f"signifie qu'un classement établi sur la moitié des joueurs ne prédit "
        f"pas le classement de l'autre moitié. Si un effet université existait, "
        f"les deux moitiés concorderaient. Ce test est le seul non circulaire "
        f"de l'analyse : contrairement à une corrélation calculée sur les "
        f"scores qui ont servi à bâtir le classement, il confronte le "
        f"classement à des données qu'il n'a pas vues.",
        MARGE,
        bas + 700000,
        CONTENU_L,
        1150000,
        couleur=ROUGE,
    )
    pied(s, "200 tirages aléatoires · graine fixée pour la reproductibilité", numero)


def slide_explication(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Pourquoi ce résultat n'est pas surprenant", "interprétation", VIOLET)

    etapes = [
        ("~1 000 000", "lycéens\njoueurs", GRIS),
        ("~75 000", "joueurs\nuniversitaires", GRIS),
        ("~16 000", "joueurs de\ndivision I", BLEU),
        ("~250", "draftés\npar an", AMBRE),
        ("1 679", "dans ce jeu\nde données", ROUGE),
    ]
    x = MARGE
    largeur_etape = (CONTENU_L - 4 * 180000) // 5
    for i, (valeur, libelle, couleur) in enumerate(etapes):
        cx = x + i * (largeur_etape + 180000)
        hauteur = 1150000
        s.rectangle(cx, Y_CONTENU, largeur_etape, hauteur, couleur=FOND_CLAIR)
        s.rectangle(cx, Y_CONTENU, largeur_etape, 46000, couleur=couleur)
        s.texte(valeur, cx + 100000, Y_CONTENU + 160000, largeur_etape - 200000,
                420000, taille=22, gras=True, couleur=MARINE,
                police=TITRE_POLICE, alignement="centre")
        s.texte(libelle, cx + 100000, Y_CONTENU + 620000, largeur_etape - 200000,
                450000, taille=11, couleur=TEXTE, police=CORPS_POLICE,
                alignement="centre", interligne=1.15)
        if i < 4:
            fx = cx + largeur_etape + 30000
            s.texte("›", fx, Y_CONTENU + 420000, 120000, 300000, taille=18,
                    gras=True, couleur=GRIS, police=CORPS_POLICE,
                    alignement="centre")

    # Exemples tirés des données, pour ne pas figer dans la diapositive des
    # noms qui deviendraient faux si le calcul évolue.
    volumes = ctx.get("volumes_universites", [])
    tete_volume = ", ".join(f"{u} ({n})" for u, n in volumes[:2]) or "n/d"
    atypiques = ctx.get("exemples_petits_programmes", [])
    exemples = " ; ".join(
        f"{j['nom']} ({j['universite']}, {j['n_universite']} joueur"
        f"{'s' if j['n_universite'] > 1 else ''} dans l'échantillon)"
        for j in atypiques[:2]
    )

    puces(
        s,
        [
            ("Le filtre a déjà opéré — ",
             "arriver en NFL suppose d'avoir franchi une sélection d'une "
             "sévérité extrême. Les joueurs comparés ici forment déjà "
             "l'extrémité de la distribution : la variabilité qui distinguait "
             "les universités a été absorbée par le recrutement."),
            ("Les grands programmes envoient plus de joueurs, pas de meilleurs "
             "joueurs — ",
             f"en tête du volume : {tete_volume}, contre une médiane de 3 "
             f"joueurs par université. Leur avantage est quantitatif ; une fois "
             f"en NFL, leurs joueurs ne surperforment pas ceux issus de petits "
             f"programmes."),
            ("Le talent individuel domine l'origine — ",
             (f"parmi les mieux notés de l'échantillon : {exemples}. "
              if exemples else "")
             + "Ces trajectoires ne sont pas des anomalies : elles illustrent "
             "que l'université n'est pas le facteur discriminant."),
        ],
        MARGE,
        Y_CONTENU + 1480000,
        CONTENU_L,
        2800000,
        taille=12.5,
    )
    pied(s, "Ordres de grandeur du parcours de sélection vers la NFL", numero)


def slide_limites(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Ce que cette analyse ne permet pas de dire", "limites", AMBRE)

    gauche = [
        ("Huit semaines, une seule saison — ",
         "les semaines 1 à 8 de 2021. Aucune validation sur une autre saison "
         "n'est possible, ni aucun suivi de progression."),
        ("Uniquement des actions de passe — ",
         "le jeu de données ne contient aucune course. Les qualités de blocage "
         "au sol ou de course après réception sont invisibles ici."),
        ("Effectifs très faibles — ",
         "médiane de 3 joueurs par université. C'est la contrainte dominante, "
         "et la raison du shrinkage."),
    ]
    droite = [
        ("Un effet nul n'est pas une preuve d'absence — ",
         "l'analyse montre qu'aucun effet n'est détectable à cette taille "
         "d'échantillon, pas qu'il est rigoureusement inexistant."),
        ("Couverture et réception mesurées indirectement — ",
         "la séparation au lâcher est un bon indicateur, mais elle ignore le "
         "schéma défensif : un défenseur en zone profonde est loin du receveur "
         "par construction."),
        ("224 joueurs sans université renseignée — ",
         "soit 13 % de l'effectif, exclus de l'analyse."),
    ]

    s.rectangle(MARGE, Y_CONTENU, CONTENU_L // 2 - 150000, 3300000, couleur=FOND_CLAIR)
    s.rectangle(MARGE + CONTENU_L // 2 + 150000, Y_CONTENU,
                CONTENU_L // 2 - 150000, 3300000, couleur=FOND_CLAIR)
    s.texte("Limites des données", MARGE + 200000, Y_CONTENU + 160000,
            CONTENU_L // 2 - 550000, 300000, taille=13, gras=True,
            couleur=AMBRE, police=CORPS_POLICE)
    s.texte("Limites de l'interprétation", MARGE + CONTENU_L // 2 + 350000,
            Y_CONTENU + 160000, CONTENU_L // 2 - 550000, 300000, taille=13,
            gras=True, couleur=AMBRE, police=CORPS_POLICE)

    puces(s, gauche, MARGE + 200000, Y_CONTENU + 560000,
          CONTENU_L // 2 - 550000, 2600000, taille=11.5)
    puces(s, droite, MARGE + CONTENU_L // 2 + 350000, Y_CONTENU + 560000,
          CONTENU_L // 2 - 550000, 2600000, taille=11.5)

    encadre(
        s,
        "La précaution qui vaut aussi pour le projet d'origine",
        "Corrélation n'est pas causalité, et ici l'absence de corrélation "
        "n'est pas l'absence de valeur ajoutée. Une université peut très bien "
        "développer un joueur sans que cela se lise dans sa performance NFL : "
        "son apport est peut-être justement ce qui lui a permis d'y accéder.",
        MARGE,
        Y_CONTENU + 3480000,
        CONTENU_L,
        1050000,
        couleur=GRIS,
    )
    pied(s, "α = 0,05 · aucune correction pour tests multiples appliquée", numero)


def slide_conclusion(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    _fond(s, MARINE)
    s.rectangle(MARGE, 500000, 1500000, 46000, couleur=AMBRE)
    s.texte("CE QU'IL FAUT RETENIR", MARGE, 700000, CONTENU_L, 320000,
            taille=12, gras=True, couleur=AMBRE, police=CORPS_POLICE,
            espacement=180)

    cl = ctx["classement_universites"]
    vm = cl.get("validation_moities", {})

    # Plage réelle des p-values par poste, calculée et non figée.
    p_values = [
        r["anova"]["p_value"]
        for r in ctx["classement_par_poste"].values()
        if r.get("applicable") and r.get("anova", {}).get("p_value") is not None
    ]
    plage = (
        f"p de {_nb(min(p_values), 2)} à {_nb(max(p_values), 2)}"
        if p_values
        else "aucun test significatif"
    )

    constats = [
        ("1", "Le score de performance fonctionne.",
         f"Validé sur une référence externe : les Pro Bowlers 2021 atteignent "
         f"le percentile {_nb(ctx['validation_faciale'].get('_global', {}).get('percentile_moyen_elite'))} "
         f"de leur groupe, contre 50 attendu au hasard.", VERT),
        ("2", "L'université n'explique pas la performance NFL.",
         f"Aucun test significatif, à aucun poste ({plage}). La "
         f"validation par moitiés donne ρ = "
         f"{_nb(vm.get('rho_moyen'), 3) if vm.get('applicable') else 'n/d'} : "
         f"le classement n'est pas reproductible.", ROUGE),
        ("3", "Les grands programmes envoient plus de joueurs, pas de meilleurs.",
         (
             ", ".join(f"{u} ({n})" for u, n in ctx.get("volumes_universites", [])[:2])
             or "Les plus gros programmes"
         )
         + " dominent le volume, contre une médiane de 3 joueurs par "
         "université, sans surperformance individuelle mesurable.", AMBRE),
        ("4", "C'est un effet de sélection, pas un démenti du rôle des universités.",
         "Le filtre d'accès à la NFL est si sévère qu'il absorbe les écarts "
         "de formation en amont.", BLEU),
    ]

    y = 1280000
    for num, titre, corps, couleur in constats:
        s.rectangle(MARGE, y, CONTENU_L, 1080000, couleur=MARINE_CLAIR)
        s.rectangle(MARGE, y, 52000, 1080000, couleur=couleur)
        s.texte(num, MARGE + 190000, y + 230000, 400000, 600000, taille=30,
                gras=True, couleur=couleur, police=TITRE_POLICE)
        s.texte(titre, MARGE + 720000, y + 170000, CONTENU_L - 950000, 340000,
                taille=15, gras=True, couleur=BLANC, police=CORPS_POLICE)
        s.texte(corps, MARGE + 720000, y + 540000, CONTENU_L - 950000, 480000,
                taille=11.5, couleur="B9C7D4", police=CORPS_POLICE,
                interligne=1.15)
        y += 1180000

    pied(s, "", numero)
    s.texte(
        f"{cl['n_joueurs']} joueurs · {cl['n_universites']} universités · "
        f"8,3 M de positions GPS · saison 2021, semaines 1 à 8",
        MARGE,
        Y_PIED,
        CONTENU_L,
        300000,
        taille=9.5,
        couleur=GRIS,
        police=CORPS_POLICE,
    )


def slide_annexe(pres: Presentation, ctx: dict, numero: int) -> None:
    s = pres.ajouter_slide()
    en_tete(s, "Reproduire l'analyse", "annexe technique", BLEU)

    puces(
        s,
        [
            ("Commande — ",
             "python main_nfl.py --donnees "
             "../../nfl-big-data-bowl-regional-event-data"),
            ("Dépendances — ",
             "aucune. L'intégralité de l'analyse, des tests statistiques et de "
             "la génération du .pptx repose sur la bibliothèque standard de "
             "Python 3.11."),
            ("Tests statistiques réimplémentés — ",
             "lois de Fisher, Student et Chi-2 par fonctions bêta et gamma "
             "incomplètes ; validés contre les valeurs de tables usuelles."),
            ("Seuils — ",
             f"50 snaps minimum par joueur, 5 joueurs minimum par université "
             f"pour le classement général, 3 pour le classement par poste."),
            ("Sorties — ",
             "scores_joueurs.csv, classement_universites.csv, "
             "statistiques.json, rapport_nfl.md, presentation_nfl.pptx"),
        ],
        MARGE,
        Y_CONTENU,
        CONTENU_L,
        2500000,
        taille=12.5,
    )

    tableau(
        s,
        ["Module", "Responsabilité"],
        [
            ["nfl_data.py", "Chargement des CSV, normalisation des universités, "
             "familles de postes"],
            ["nfl_tracking.py", "Balayage des 8,3 M lignes de tracking : "
             "athlétisme et séparation"],
            ["nfl_metrics.py", "Scores en percentile intra-poste, agrégation et "
             "shrinkage"],
            ["nfl_stats.py", "ANOVA, Chi-2, Welch, Spearman, shrinkage, "
             "validation par moitiés"],
            ["pptx_builder.py", "Écriture du paquet OOXML (.pptx) en ZIP + XML"],
            ["pptx_validator.py", "Contrôle d'intégrité du fichier produit"],
        ],
        MARGE,
        Y_CONTENU + 2650000,
        [2600000, CONTENU_L - 2600000],
        hauteur_ligne=300000,
        taille=10.5,
    )
    pied(s, "Code et données : dépôt Madacoeur/NFL", numero)


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def construire(ctx: dict, chemin: str) -> tuple[str, int]:
    """Construit et enregistre la présentation. Retourne (chemin, n_slides)."""
    pres = Presentation(
        titre="Performance des joueurs NFL par poste et par université",
        auteur="Analyse NFL Big Data Bowl",
    )

    slide_couverture(pres, ctx)
    numero = 2
    slide_question(pres, numero); numero += 1
    slide_donnees(pres, ctx, numero); numero += 1
    slide_methode(pres, numero); numero += 1
    slide_indicateurs(pres, ctx, numero); numero += 1
    slide_validation(pres, ctx, numero); numero += 1

    for role in nfl_data.ORDRE_GROUPES:
        if ctx["meilleurs_joueurs"].get(role):
            slide_groupe(pres, role, ctx, numero)
            numero += 1

    slide_classement_general(pres, ctx, numero); numero += 1
    slide_effet_reel(pres, ctx, numero); numero += 1
    slide_split_half(pres, ctx, numero); numero += 1
    slide_explication(pres, ctx, numero); numero += 1
    slide_limites(pres, ctx, numero); numero += 1
    slide_conclusion(pres, ctx, numero); numero += 1
    slide_annexe(pres, ctx, numero)

    pres.enregistrer(chemin)
    return chemin, len(pres.slides)
