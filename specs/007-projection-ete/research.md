# Recherche : Projection de l'orniérage été par été (007)

Données et calculs vérifiés le 2026-09-29.

## R1. Données climatiques : relevés quotidiens de Météo-France

- **Source** : [Données climatologiques de base quotidiennes](https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes)
  (Météo-France, Licence Ouverte 2.0), fichiers par département hébergés en France
  (OVH, Strasbourg) ; pour Paris : `Q_75_previous-1950-2024_RR-T-Vent` et
  `Q_75_latest-2025-2026_RR-T-Vent` (mis à jour le 2026-09-28 : **l'été 2026 est publié**).
- **Station de référence** : Paris-Montsouris (`75114001`), série continue depuis 1867,
  représentative de l'agglomération ; partagée avec 004 (`sources/meteo.py`).

## R2. Sévérité d'un été : degrés-jours au-dessus de 30 °C

- **Décision** : sévérité = somme, de juin à août, de `max(0, TX − 30 °C)` (température
  maximale quotidienne). Au-dessus de 30 °C à l'ombre, la surface d'un enrobé au soleil
  dépasse couramment 50 °C, domaine où il se déforme sous charge ; le seuil est un réglage.
- **Valeurs à Paris-Montsouris** (calculées sur les fichiers ci-dessus) :

| Été | Jours ≥ 30 °C | Jours ≥ 35 °C | Degrés-jours > 30 °C |
|---|---|---|---|
| Moyenne 2016–2025 | 17,3 | — | **49,8** |
| 2019 | 20 | 4 | 77,2 |
| 2022 | 22 | 5 | **78,5** |
| 2003 | 21 | 10 | 99,9 |
| 2026 | 39 | 20 | **196,3** |

- **Scénarios** (FR-002) : **été moyen** = moyenne des dix derniers étés complets
  (2016–2025, recalculée chaque année) ; **été chaud** = 2022 (≈ 2019) ; **été très chaud** =
  **2026**, le plus sévère observé, près du double de 2003, et celui après lequel
  l'orniérage de « Paix - Verdun » a été constaté. 2003 se situe entre « chaud » et « très
  chaud ».

## R3. Score projeté

- **Décision** : pour le point `p` et l'été `n` (1 = été suivant le rapport) :

  `S(p, n) = S(p, n−1) × (1 + k × r_n × h_p × G(p, n))`, avec `S(p, 0)` = score du rapport,

  - `r_n` = degrés-jours de l'été du scénario / degrés-jours de l'été moyen ;
  - `h_p` = sensibilité du point à la chaleur = produit de ses effets ensoleillement et
    chaleur du rapport, divisé par la moyenne de la commune (0,73 à 1,17 à Courbevoie) :
    un point exposé accélère davantage lors d'un été chaud, ce qui peut faire changer
    l'ordre entre scénarios ;
  - `G(p, n)` = rapport de charge avec l'hypothèse de fréquentation `g` :
    `ln(1 + bus × (1 + g)^n) / ln(1 + bus)` (1 si stable).
- **Propriétés** (FR-008, SC-003) : croissant avec la sévérité de l'été et la fréquentation ;
  jamais décroissant d'un été à l'autre.
- **Réfection** (cas limite) : si un relevé de 003 indique une réfection après la date du
  rapport, le score du point repart de son score sans l'effet d'âge de l'enrobé, à l'été
  suivant la réfection.

## R4. Calage initial du coefficient `k` (SC-002)

- « Paix - Verdun » (A23742), méthode 1.2 : score **77**, rang 10, `h_p` = 0,968.
- Pour atteindre 95 dès le premier été du scénario très chaud (`r` = 196,3 / 49,8 = 3,94) :
  `k ≥ (95 / 77 − 1) / (3,94 × 0,968)` ⇒ **`k = 0,062`**.
- Effet d'un été sur un point d'exposition moyenne : ≈ **+6 %** (moyen), **+10 %** (chaud),
  **+24 %** (très chaud).
- **Limite assumée** : calage sur un seul point constaté ; `k`, le seuil de 30 °C et le seuil
  d'intervention (95) seront recalés avec les relevés de 003 (points dont l'orniérage
  s'aggrave entre deux relevés, SC-006). Chaque recalage = nouvelle version de la méthode de
  projection, décrite dans le journal des changements de méthode.

## R5. Calcul à la demande, sans stockage

- **Décision** : la projection est calculée par l'API à l'ouverture de la page, à partir du
  `points.geojson` du rapport (score, effets d'ensoleillement et de chaleur, charge) et des
  sévérités d'été mises en cache : quelques millisecondes par commune ; l'hypothèse de
  fréquentation est un paramètre de la page ; rien n'est stocké (reproductible : même
  rapport, mêmes données, même hypothèse ⇒ même résultat, FR-012).
- **Courbes** : SVG produit côté serveur (aucun script client), page et export CSV.
- **Alternative écartée** : calcul dans le job de lot (inutile : pas de coût, pas de source
  à acquérir au moment de la demande).

## R6. Versions

- **Décision** : méthode de projection versionnée à part (`PROJECTION 1.0`) : `k`, seuil
  30 °C, seuil d'intervention 95, choix des étés ; affichée dans la page et l'export ;
  entrée dans `docs/methode/CHANGELOG.md`.
