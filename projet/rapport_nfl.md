# Performance des joueurs NFL par poste et par université

> Analyse produite par `main_nfl.py` — données NFL Big Data Bowl 2023 (saison 2021, semaines 1 à 8).

## Question

L'université d'origine d'un joueur a-t-elle un effet mesurable sur sa performance en NFL, poste par poste ?

## Réponse courte

**Non.** Le score de performance construit ici est valide — il identifie correctement les joueurs d'élite (percentile moyen 79.5 pour les Pro Bowlers 2021, contre 50 attendu au hasard). Mais aucun test ne détecte d'effet de l'université sur la performance, à aucun poste.

## Périmètre retenu

- Joueurs référencés : **1679**
- Sans université renseignée (exclus) : **224**
- Retenus après filtrage : **987** (≥ 50 snaps)
- Universités classées : **66** (≥ 5 joueurs)
- Lignes de tracking traitées : **8 314 178**
- Durée d'exécution : **14 s**

## Composition du score

| Composante | Poids | Calcul |
|---|---|---|
| Production | 50 % | Indicateur propre au poste, en percentile intra-poste |
| Athlétisme | 25 % | Vitesse et accélération de pointe (tracking) |
| Temps de jeu | 25 % | Nombre de snaps joués |

### Indicateur de production par poste

| Groupe | Indicateur | Sens favorable | Joueurs |
|---|---|---|---|
| Pass rush | Taux de pression générée | plus haut | 227 |
| Protection | Taux de pression concédée | plus bas | 188 |
| Couverture | Distance de couverture au lâcher | plus bas | 298 |
| Réception | Séparation au lâcher | plus haut | 243 |
| Quarterback | Efficacité de passe | plus haut | 31 |

## Validation du score

Contrôle de validité externe : on vérifie que les joueurs sélectionnés en Pro Bowl ou All-Pro en 2021 ressortent effectivement en haut de leur groupe.

| Groupe | Joueurs d'élite retrouvés | Percentile moyen | Part dans le tiers supérieur |
|---|---|---|---|
| Pass rush | 8/8 | 95.4 | 100 % |
| Protection | 8/8 | 76.3 | 75 % |
| Couverture | 7/7 | 80.1 | 71 % |
| Quarterback | 7/7 | 66.1 | 57 % |

## Meilleurs joueurs par poste

### Pass rush

| # | Joueur | Poste | Université | Score | Taux de pression générée |
|---|---|---|---|---|---|
| 1 | Kenny Clark | NT | UCLA | 93.9 | 0.147 |
| 2 | Maxx Crosby | DE | Eastern Michigan | 93.8 | 0.225 |
| 3 | Trey Hendrickson | DE | Florida Atlantic | 93.7 | 0.208 |
| 4 | Shaquil Barrett | OLB | Colorado State | 92.5 | 0.189 |
| 5 | Aaron Donald | DT | Pittsburgh | 92.3 | 0.146 |

### Protection

| # | Joueur | Poste | Université | Score | Taux de pression concédée |
|---|---|---|---|---|---|
| 1 | Tristan Wirfs | T | Iowa | 92.4 | 0.026 |
| 2 | Corey Linsley | C | Ohio State | 90.4 | 0.015 |
| 3 | Andrew Norwell | G | Ohio State | 85.6 | 0.011 |
| 4 | Brian O'Neill | T | Pittsburgh | 85.5 | 0.020 |
| 5 | Joe Thuney | G | North Carolina State | 85.3 | 0.029 |

### Couverture

| # | Joueur | Poste | Université | Score | Distance de couverture au lâcher |
|---|---|---|---|---|---|
| 1 | Marshon Lattimore | CB | Ohio State | 87.9 | 2.024 |
| 2 | Cole Holcomb | OLB | North Carolina | 87.5 | 3.556 |
| 3 | Kenny Young | ILB | UCLA | 86.5 | 3.590 |
| 4 | Chauncey Gardner-Johnson | SS | Florida | 85.1 | 2.160 |
| 5 | Xavien Howard | CB | Baylor | 84.9 | 2.383 |

### Réception

| # | Joueur | Poste | Université | Score | Séparation au lâcher |
|---|---|---|---|---|---|
| 1 | Mike Davis | RB | South Carolina | 94.3 | 7.366 |
| 2 | Marquise Brown | WR | Oklahoma | 89.6 | 3.506 |
| 3 | Michael Pittman | WR | Southern California | 88.2 | 3.186 |
| 4 | Mecole Hardman | WR | Georgia | 85.5 | 3.219 |
| 5 | Noah Fant | TE | Iowa | 84.5 | 3.027 |

### Quarterback

| # | Joueur | Poste | Université | Score | Efficacité de passe |
|---|---|---|---|---|---|
| 1 | Matt Ryan | QB | Boston College | 77.0 | 0.526 |
| 2 | Derek Carr | QB | Fresno State | 77.0 | 0.506 |
| 3 | Kirk Cousins | QB | Michigan State | 74.6 | 0.539 |
| 4 | Tom Brady | QB | Michigan | 69.8 | 0.520 |
| 5 | Teddy Bridgewater | QB | Louisville | 69.8 | 0.487 |

## Classement des universités (tous postes)

Le score régularisé corrige l'effet de taille d'échantillon (shrinkage bayésien empirique). C'est lui qui fait foi.

| # | Université | Joueurs | Score brut | Score régularisé | p-value |
|---|---|---|---|---|---|
| 1 | Ohio State | 29 | 58.4 | 52.6 | 0.050 |
| 2 | Louisiana State | 34 | 54.8 | 51.9 | 0.224 |
| 3 | Kansas State | 7 | 65.4 | 51.9 | 0.020 |
| 4 | Maryland | 8 | 63.2 | 51.9 | 0.035 |
| 5 | Texas A&M | 14 | 56.8 | 51.7 | 0.365 |
| 6 | Brigham Young | 5 | 64.8 | 51.6 | 0.056 |
| 7 | UCLA | 13 | 56.6 | 51.6 | 0.386 |
| 8 | Georgia | 21 | 54.4 | 51.6 | 0.486 |
| 9 | Utah | 12 | 56.4 | 51.5 | 0.393 |
| 10 | Texas Tech | 6 | 60.5 | 51.5 | 0.116 |
| 11 | Southern California | 14 | 55.3 | 51.5 | 0.351 |
| 12 | Mississippi State | 16 | 54.7 | 51.5 | 0.564 |
| 13 | Duke | 6 | 58.4 | 51.4 | 0.305 |
| 14 | Southern Methodist | 6 | 58.3 | 51.4 | 0.112 |
| 15 | Nebraska | 5 | 59.2 | 51.3 | 0.534 |

## Tests statistiques

| Test | Statistique | p-value | Effet détecté |
|---|---|---|---|
| ANOVA globale | F = 0.838 | 0.8133 | non |
| Chi-2 d'indépendance | V de Cramér = 0.283 | 0.6875 | non |
| ANOVA · Pass rush | F = 0.784 | 0.7666 | non |
| ANOVA · Protection | F = 0.667 | 0.8498 | non |
| ANOVA · Couverture | F = 1.174 | 0.2398 | non |
| ANOVA · Réception | F = 0.771 | 0.7869 | non |

### Validation par moitiés (test non circulaire)

On coupe au hasard les joueurs de chaque université en deux moitiés, on classe les universités sur la première, et on mesure si ce classement prédit celui de la seconde. Répété 200 fois.

- ρ moyen : **-0.063** (négligeable)
- Tirages à corrélation positive : **23 %**
- Étendue : -0.340 à +0.214

Un ρ proche de zéro signifie que le classement n'est pas reproductible : il reflète le bruit d'échantillonnage.

## Pourquoi ce résultat

Les joueurs comparés ont tous franchi un filtre de sélection d'une sévérité extrême (environ 250 draftés par an pour 75 000 joueurs universitaires). La variabilité qui distinguait les universités a été absorbée en amont par le recrutement. Les grands programmes envoient **plus** de joueurs en NFL (Alabama 47, LSU 43, contre 3 en médiane) sans que ces joueurs y soient **meilleurs**.

## Limites

- Huit semaines d'une seule saison : aucune validation croisée possible
- Actions de passe uniquement : aucune course dans le jeu de données
- Médiane de 3 joueurs par université : contrainte dominante
- Un effet non détecté n'est pas un effet nul démontré
- Couverture et réception évaluées via la séparation au lâcher, qui ignore le schéma défensif
- 224 joueurs sans université renseignée, exclus

## Reproduire

```bash
python main_nfl.py --donnees ../../nfl-big-data-bowl-regional-event-data
```

Aucune dépendance externe : bibliothèque standard de Python 3.11 uniquement, y compris pour les tests statistiques et la génération du fichier PowerPoint.
