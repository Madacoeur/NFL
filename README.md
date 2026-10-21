# Analyse de corrélation Université ↔ Réussite professionnelle

Système clé en main qui identifie les universités produisant les meilleurs taux
de réussite professionnelle par domaine, et détermine s'il existe une
corrélation **statistiquement significative** entre l'université de formation et
la réussite professionnelle.

## Ce que fait le système

1. **Charge** un fichier CSV de diplômés.
2. **Nettoie** les données : normalisation des noms d'universités, gestion des
   valeurs manquantes, suppression des doublons, winsorisation des outliers
   salariaux, filtrage des universités sous-représentées.
3. **Calcule** un score de réussite composite par diplômé.
4. **Teste** statistiquement l'effet de l'université (ANOVA, Chi-carré,
   Spearman, régression multiple).
5. **Génère** visualisations, rapport Markdown, CSV enrichi et JSON de stats.

## Installation

### Option A — avec `uv` (recommandé, rapide)

```bash
uv venv .venv --python 3.12
uv pip install --python .venv -r requirements.txt
```

### Option B — avec `pip` classique

```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Utilisation

### Lancement en une commande

```bash
# Avec votre propre fichier
python main.py --input data/input/donnees_diplomes.csv

# Génère d'abord un jeu de données synthétique (1500 obs.) puis analyse
python main.py --generate
```

Si le fichier `--input` n'existe pas, le système génère automatiquement un jeu
synthétique à cet emplacement.

### Options

| Option | Défaut | Description |
|---|---|---|
| `--input` | `data/input/donnees_diplomes.csv` | Chemin du CSV d'entrée |
| `--generate` | `false` | Génère un jeu synthétique avant l'analyse |
| `--n` | `1500` | Nombre d'observations à générer (`--generate`) |
| `--seed` | `42` | Graine aléatoire du générateur |
| `--min-obs` | `30` | Observations minimum par université (filtrage) |

Avec l'environnement `uv` sans activation :

```bash
.venv/bin/python main.py --generate
```

## Format du CSV d'entrée

| Colonne | Type | Requis | Description |
|---|---|---|---|
| `id` | entier | ✅ | Identifiant unique |
| `nom` | texte | ❌ | Optionnel (confidentialité) |
| `universite` | texte | ✅ | Université de formation |
| `annee_diplome` | entier | ✅ | Année d'obtention |
| `domaine_formation` | texte | ❌ | Domaine d'études |
| `poste_actuel` | texte | ❌ | Intitulé du poste |
| `domaine_professionnel` | texte | ✅ | Secteur d'activité |
| `annees_experience` | entier | ✅ | Années d'expérience |
| `salaire_annuel` | nombre | ✅ | Salaire brut annuel (€) |
| `niveau_poste` | 1-6 | ✅ | 1=Junior … 6=C-Level |
| `taille_entreprise` | entier | ✅ | Effectif de l'entreprise |
| `satisfaction_carriere` | 1-10 | ❌ | Score de satisfaction |

Les colonnes optionnelles absentes ou vides sont tolérées.

## Fichiers produits

```
data/output/scores_calcules.csv        # données enrichies (scores par diplômé)
data/output/resume_universite_domaine.csv
data/output/statistiques.json          # toutes les statistiques détaillées
visualizations/*.png                   # graphiques
rapport_final.md                       # rapport complet
```

## Le score de réussite

Score global = moyenne pondérée de trois sous-scores (chacun sur 0-100) :

| Sous-score | Poids | Calcul |
|---|---|---|
| **Salarial** | 40% | Percentile du salaire **dans son domaine** |
| **Hiérarchique** | 35% | Niveau de poste normalisé (1-6 → 0-100) |
| **Vitesse** | 25% | Percentile de la progression (niveau / ancienneté) |

Le percentile intra-domaine garantit une comparaison équitable entre secteurs
aux échelles salariales différentes.

## Analyses statistiques

- **ANOVA** (globale et par domaine) : les moyennes de réussite diffèrent-elles
  entre universités ? (F-statistic, p-value)
- **Chi-carré** : indépendance entre université et catégorie de réussite
  (Faible / Moyen / Élevé) ; taille d'effet via **V de Cramér**.
- **Spearman** : corrélation entre le rang de l'université et le score. Rang
  élevé = mieux classé, donc un ρ positif indique « mieux classé ↔ meilleur score ».
- **Régression linéaire multiple** : isole l'effet net de l'université en
  contrôlant années d'expérience, domaine et taille d'entreprise. L'effet du
  facteur université est testé par un **F de type II**.
- **Classements par domaine** : score moyen, **IC 95 %**, test t one-vs-rest
  (p-value) et taille d'effet **Cohen's d**.

## Interpréter les résultats

- **p-value < 0.05** : résultat statistiquement significatif.
- **Cohen's d** : < 0.2 négligeable · 0.2-0.5 petite · 0.5-0.8 moyenne · > 0.8 grande.
- **V de Cramér / ρ** : < 0.1 négligeable · 0.1-0.3 faible · 0.3-0.5 modérée · > 0.5 forte.
- **R² (régression)** : part de variance du score expliquée par le modèle.
- La **conclusion principale** du rapport croise ANOVA, régression et Chi-carré :
  « OUI » si au moins deux signaux concordent, « PARTIELLEMENT » pour un seul,
  « NON » sinon.

> ⚠️ Corrélation n'est pas causalité. Un effet « université significatif » peut
> refléter la sélection à l'entrée autant que la valeur ajoutée de la formation.
> Méfiez-vous aussi des universités à faible `n` (IC larges).

## Structure du projet

```
projet/
├── data/
│   ├── input/donnees_diplomes.csv
│   └── output/{scores_calcules.csv, resume_universite_domaine.csv, statistiques.json}
├── src/
│   ├── data_generator.py        # jeu de données synthétique
│   ├── data_processing.py       # nettoyage et préparation
│   ├── metrics.py               # calcul des scores
│   ├── statistical_analysis.py  # tests statistiques
│   ├── visualizations.py        # graphiques
│   └── report_generator.py      # rapport Markdown + JSON
├── visualizations/*.png
├── rapport_final.md
├── requirements.txt
└── main.py                      # point d'entrée
```

## Jeu de données synthétique

`src/data_generator.py` produit 18 universités françaises réelles sur 7 domaines,
avec une corrélation **volontairement injectée** (les universités prestigieuses
produisent des réussites plus élevées) afin de valider la capacité de détection.
Il introduit aussi valeurs manquantes, doublons et variantes de noms pour
éprouver le nettoyage.

## Validation

- ✅ Toutes les visualisations générées sans erreur (12 PNG)
- ✅ p-values cohérentes ; corrélation injectée correctement détectée
- ✅ Classements avec IC 95 % et tailles d'effet
- ✅ Cas limites gérés (peu de données, filtrage total, université unique)
- ✅ Temps d'exécution < 30 s pour 2000 observations (~8-9 s pour 1500)

## Performance

Environ 8-9 secondes pour 1500 observations sur une machine standard, tests
statistiques et 12 graphiques inclus.
