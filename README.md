# Une même méthode, deux terrains

Ce dépôt contient deux analyses qui posent la **même question statistique** avec
la **même ossature méthodologique**, sur deux jeux de données différents :

> *L'établissement de formation a-t-il un effet mesurable sur la réussite
> ultérieure, une fois comparés des individus réellement comparables ?*

| Volet | Terrain | Données | Point d'entrée |
|---|---|---|---|
| **1. Universités ↔ carrières** | Diplômés français | Synthétiques (corrélation injectée) | `projet/main.py` |
| **2. Universités ↔ performance NFL** | Joueurs de football américain | Réelles (NFL Big Data Bowl 2023) | `projet/main_nfl.py` |

Le volet 2 est une transposition du volet 1 : les diplômés deviennent des
joueurs, les domaines professionnels deviennent des postes, et le salaire est
remplacé par une mesure de performance reconstruite depuis des données de
terrain.

---

## Volet 2 — Performance des joueurs NFL par poste et par université

### La question

Quelles universités produisent les joueurs les plus performants, **poste par
poste** ? Et cet écart est-il statistiquement réel ?

### La réponse

**Le score de performance fonctionne, mais l'université n'explique pas la
performance NFL.**

- **Score validé** sur une référence externe : les joueurs sélectionnés en Pro
  Bowl / All-Pro en 2021 atteignent le **percentile 79,5** de leur groupe, contre
  50 attendu si le score était du bruit. En pass rush, les 8 joueurs d'élite
  recherchés sont tous dans le tiers supérieur.
- **Aucun effet université détecté**, à aucun poste : ANOVA de p = 0,24 à 0,85.
- **Classement non reproductible** : la validation par moitiés donne
  **ρ = −0,06**. Un classement établi sur la moitié des joueurs ne prédit pas
  celui de l'autre moitié.
- **Interprétation** : les grands programmes envoient **plus** de joueurs en NFL
  (Alabama 48, LSU 43, contre une médiane de 3) sans que ces joueurs y soient
  **meilleurs**. Le filtre d'accès à la NFL absorbe en amont les écarts de
  formation.

### Lancer l'analyse

```bash
cd projet
python main_nfl.py --donnees ../../nfl-big-data-bowl-regional-event-data
```

**Aucune dépendance externe.** L'intégralité du volet 2 — chargement des
données, tests statistiques, et génération du fichier PowerPoint — repose sur la
seule bibliothèque standard de Python 3.11.

| Option | Défaut | Description |
|---|---|---|
| `--donnees` | dépôt voisin | Racine des données Big Data Bowl |
| `--min-snaps` | `50` | Snaps minimum pour qu'un joueur soit retenu |
| `--min-joueurs` | `5` | Joueurs minimum par université (classement général) |
| `--min-joueurs-poste` | `3` | Joueurs minimum par université (classement par poste) |
| `--limite-matchs` | — | Limite les fichiers tracking lus (mise au point) |
| `--sans-pptx` | `false` | N'écrit pas la présentation |

### Livrables produits

```
projet/presentation_nfl.pptx          18 diapositives
projet/rapport_nfl.md                 rapport complet
projet/data/output/scores_joueurs.csv            987 joueurs notés
projet/data/output/classement_universites.csv    66 universités
projet/data/output/classement_par_poste.csv      classement par groupe
projet/data/output/statistiques_nfl.json         toutes les statistiques
```

### Le score de performance

Score sur 0-100, moyenne pondérée de trois composantes :

| Composante | Poids | Calcul |
|---|---|---|
| **Production** | 50 % | Indicateur propre au poste (voir ci-dessous) |
| **Athlétisme** | 25 % | Vitesse et accélération de pointe (tracking GPS) |
| **Temps de jeu** | 25 % | Nombre de snaps joués |

Chaque composante est convertie en **percentile à l'intérieur de la famille de
postes** du joueur — jamais sur l'ensemble des joueurs. C'est la transposition
directe du « percentile intra-domaine » du volet 1, et la précaution est
indispensable : un running back qui sort du backfield obtient mécaniquement
5,6 yards de séparation là où un wide receiver affronte un cornerback à
2,5 yards. Les noter sur la même échelle conduirait à conclure que les running
backs sont les meilleurs receveurs de la ligue.

### Indicateur de production par poste

| Groupe | Postes | Indicateur | Sens favorable |
|---|---|---|---|
| Pass rush | DE, DT, NT, OLB | Taux de pression générée (sacks + hits + hurries) / snaps | plus haut |
| Protection | T, G, C | Taux de pression concédée | plus bas |
| Couverture | CB, FS, SS, ILB | Distance au receveur le plus proche au lâcher | plus bas |
| Réception | WR, TE, RB | Séparation obtenue au lâcher | plus haut |
| Quarterback | QB | Complétion − sacks − 2 × interceptions | plus haut |

Le groupe d'un joueur est déduit du **rôle PFF réellement tenu** sur ses snaps,
pas de son étiquette de poste : les 136 outside linebackers du jeu de données se
scindent naturellement en 82 pass rushers et 54 défenseurs de couverture.

Les données PFF ne notent la production que des pass rushers et des bloqueurs.
Pour les receveurs et les défenseurs de couverture, l'indicateur est reconstruit
depuis le tracking : à la frame exacte où le quarterback lâche le ballon, on
calcule la distance entre chaque receveur et le défenseur le plus proche. Cela
rend 541 joueurs supplémentaires évaluables.

### Rigueur statistique

- **Shrinkage bayésien empirique** — la médiane est de 3 joueurs par université.
  Une moyenne brute sur 3 joueurs n'est pas comparable à une moyenne sur 34 : les
  scores des petits effectifs sont tirés vers la moyenne générale. Quand la
  dispersion inter-universités n'excède pas le bruit d'échantillonnage, le code
  le signale (`signal_detectable`) au lieu de publier un classement plat.
- **Validation par moitiés** — le seul test non circulaire de l'analyse. On coupe
  les joueurs de chaque université en deux moitiés au hasard, on classe sur la
  première et on vérifie si ce classement prédit la seconde, 200 fois.
- **Validation de face** — contrôle externe sur les sélections Pro Bowl /
  All-Pro 2021, qui ne proviennent pas du jeu de données.
- **Tests réimplémentés et vérifiés** — scipy étant indisponible, les lois de
  Fisher, Student et Chi-2 sont recalculées par fonctions bêta et gamma
  incomplètes, et validées contre les valeurs de tables usuelles.

### Limites

- Huit semaines d'une seule saison : aucune validation inter-saisons possible
- Actions de passe uniquement — le jeu de données ne contient aucune course
- Médiane de 3 joueurs par université : contrainte dominante de l'analyse
- 224 joueurs (13 %) sans université renseignée, exclus
- Un effet non détecté n'est pas un effet nul démontré
- La séparation au lâcher ignore le schéma défensif : un défenseur en zone
  profonde est loin du receveur par construction

### Organisation du code

| Module | Responsabilité |
|---|---|
| `src/nfl_data.py` | Chargement des CSV, normalisation des universités, familles de postes |
| `src/nfl_tracking.py` | Balayage des 8,3 M lignes de tracking : athlétisme et séparation |
| `src/nfl_metrics.py` | Scores en percentile intra-poste, agrégation, shrinkage |
| `src/nfl_stats.py` | ANOVA, Chi-2, Welch, Spearman, shrinkage, validation par moitiés |
| `src/nfl_slides.py` | Composition des 18 diapositives |
| `src/pptx_builder.py` | Écriture du paquet OOXML (.pptx) : ZIP + XML |
| `src/pptx_validator.py` | Contrôle d'intégrité et de géométrie du fichier produit |

### Génération du PowerPoint sans bibliothèque

`python-pptx` étant indisponible, `pptx_builder.py` écrit directement
l'archive OOXML (ECMA-376) : types de contenu, relations, masque, disposition,
thème et diapositives. Les graphiques sont des **formes natives PowerPoint**
(rectangles, traits, zones de texte) et non des images — le rendu reste net à
tout niveau de zoom et chaque élément demeure éditable.

Comme aucun logiciel ne peut ouvrir le fichier dans l'environnement de
génération, `pptx_validator.py` le contrôle mécaniquement : intégrité de
l'archive, bonne formation de chaque XML, complétude des types de contenu,
résolution de toutes les relations, cohérence du nombre de diapositives, et
**détection des formes débordant du cadre** — ce dernier contrôle remplaçant
l'inspection visuelle.

---

## Volet 1 — Universités ↔ réussite professionnelle

Analyse d'origine, sur données synthétiques. Documentation détaillée :
[`projet/README.md`](projet/README.md).

```bash
cd projet
pip install -r requirements.txt   # pandas, numpy, scipy, statsmodels, matplotlib, seaborn
python main.py --generate
```

Score composite (salaire 40 % en percentile intra-domaine, niveau hiérarchique
35 %, vitesse de progression 25 %), puis ANOVA, Chi-carré, Spearman et
régression linéaire multiple pour isoler l'effet de l'université en contrôlant
l'expérience, le domaine et la taille d'entreprise.

> ⚠️ Les données du volet 1 sont **synthétiques**, avec une corrélation
> volontairement injectée afin de valider la capacité de détection de la chaîne.
> Les conclusions du volet 1 portent donc sur l'outil, pas sur le monde réel.
> Celles du volet 2 portent sur des données mesurées.

## Source des données du volet 2

NFL Big Data Bowl 2023 — tracking Next Gen Stats et notation Pro Football Focus,
saison 2021, semaines 1 à 8. Le jeu de données est attendu dans un dépôt voisin
`nfl-big-data-bowl-regional-event-data`.
