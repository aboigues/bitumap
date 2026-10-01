# Feature Specification: Méthode v2 (ensoleillement, chaleur, type de route)

**Feature Branch**: `004-methode-v2`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "004 — Méthode v2 : ensoleillement LiDAR HD, îlots de chaleur approfondis, type de route intégré au score (feuille de route du README, section « Méthode de score »)."

## Contexte

La méthode 1.x reprend celle du prototype, avec des limites connues et documentées
(`docs/methode/CHANGELOG.md`) :

- **Ensoleillement** : hauteurs d'arbres et de tabliers forfaitaires, pas de relief, un seul
  jour (15 juillet) ; la version 1.2 a montré qu'un détail géométrique (un pont, la position
  du poteau) peut faire passer un point de Critique à À surveiller.
- **Chaleur** : l'aléa d'îlot de chaleur de 2022 est **peu discriminant** (effet de ×0,92 à
  ×1,07 à Courbevoie) ; il ne suit ni les étés récents ni la minéralisation locale.
  L'orniérage constaté à « Paix - Verdun » a été attribué aux canicules de l'été 2026.
- **Type de route** : affiché et filtrable, mais **sans effet sur le score** ; le trafic
  poids lourds hors bus n'est pas compté.

La méthode v2 corrige ces limites. C'est un changement de méthode majeur : les rapports
existants ne sont plus réutilisés, et chaque changement de niveau doit être explicable
(constitution, principe IV).

Hors périmètre : la projection été par été (007, qui réutilisera les données climatiques de
004), les relevés terrain eux-mêmes (003), le parcours de surveillance (006).

## Clarifications

### Session 2026-09-30

- Q: Quelles sources suffisent pour considérer qu'une réfection est « confirmée » et appliquer
  l'effet sur le score ? → A: Relevés terrain de 003 seulement, avec une année de réfection de
  source « constatée » ou « services techniques » (FR-016).
- Q: Jusqu'à combien d'années après les travaux une réfection confirmée doit-elle faire
  descendre le point ? → A: Effet dégressif : plein l'année des travaux, s'annulant au bout de
  10 ans (FR-017).
- Q: À effet plein (l'année des travaux), de combien la réfection confirmée doit-elle réduire
  le score du point ? → A: ×0,5, comme la dalle béton, puis retour linéaire à ×1,0 en 10 ans
  (FR-017).
- Q: Si le dernier relevé d'un point donne à la fois une réfection récente et un orniérage
  « marqué » ou « grave », la réfection doit-elle quand même faire descendre le point ? → A:
  Non : l'effet est annulé si le relevé le plus récent, postérieur aux travaux, constate un
  orniérage « marqué » ou « grave » (FR-018).

## User Scenarios & Testing *(mandatory)*

Acteurs :

- **Demandeur** : agent de collectivité ou de bureau d'études qui lit le rapport d'une
  commune pour décider où aller relever.
- **Mainteneur** : responsable de la méthode ; décide de sa mise en service après
  validation.

### User Story 1 - Un ensoleillement qui correspond à la rue réelle (Priority: P1)

Le demandeur lit, pour chaque point, les heures de soleil sur la chaussée l'été. Ce chiffre
tient compte de ce qui fait réellement de l'ombre : bâtiments, arbres et ouvrages avec leur
hauteur mesurée, relief, orientation de la rue, et course du soleil sur toute la période
chaude, pas seulement un jour. Il est mesuré sur la chaussée où roulent et s'arrêtent les
bus.

**Why this priority**: l'ensoleillement pèse jusqu'à ×0,8 à ×1,2 sur le score ; ses défauts
actuels déplacent des points entre niveaux (issue #18).

**Independent Test**: sur un échantillon de points dont l'ensoleillement a été observé (ombre
d'un pont, rue canyon, place dégagée, alignement d'arbres), comparer les heures calculées aux
observations.

**Acceptance Scenarios**:

1. **Given** un point sous un alignement d'arbres hauts, **When** le rapport est généré,
   **Then** l'ensoleillement tient compte de la hauteur mesurée des arbres, et non d'une
   hauteur forfaitaire.
2. **Given** deux points identiques dans des rues d'orientation différente (est-ouest et
   nord-sud), **When** le rapport est généré, **Then** leurs heures de soleil diffèrent comme
   la course du soleil l'impose.
3. **Given** la fiche d'un point, **When** le demandeur lit l'ensoleillement, **Then** il
   voit les heures de soleil sur la période chaude et ce qui fait l'ombre principale
   (bâtiment, arbre, ouvrage, relief).

---

### User Story 2 - Une chaleur qui distingue vraiment les points (Priority: P1)

Le demandeur voit pour chaque point une exposition à la chaleur qui reflète les étés
récents et le contexte immédiat : température de surface mesurée l'été, minéralisation
autour du point, contexte urbain, et exposition aux canicules. Chaque indicateur n'est
retenu que s'il a montré qu'il aide à prédire l'orniérage.

**Why this priority**: l'orniérage est d'abord un phénomène de chaleur ; un facteur chaleur
qui varie de ±7 % ne distingue presque pas les points.

**Independent Test**: sur les points à orniérage constaté et ceux sans orniérage, comparer la
capacité du facteur chaleur v1 et v2 à les séparer.

**Acceptance Scenarios**:

1. **Given** deux points de même trafic, l'un sur une place minérale sans arbre, l'autre
   dans une rue arborée, **When** le rapport est généré, **Then** l'exposition à la chaleur du
   premier est nettement plus forte, avec l'explication.
2. **Given** un nouvel été mesuré (température de surface, canicules), **When** les données
   de l'été sont disponibles, **Then** les rapports suivants en tiennent compte et indiquent
   l'été de référence.
3. **Given** un indicateur candidat (par exemple la chaleur rejetée par les climatiseurs),
   **When** son apport à la prédiction n'est pas démontré ou ses données ne sont pas
   disponibles ouvertement, **Then** il n'est pas intégré, et le journal de méthode
   l'indique avec la raison.

---

### User Story 3 - Le trafic poids lourds mesuré pris en compte (Priority: P2)

Le demandeur voit le trafic poids lourds hors bus, que la méthode 1.x ignore, intervenir dans
le score là où il est **mesuré** : l'effet repose sur les comptages de poids lourds publiés
en données ouvertes pour la voie du point. Là où aucun comptage n'existe, l'effet est neutre
et marqué « non évalué ». Le type de route reste affiché, et la fiche explique l'effet
appliqué et la source du comptage.

**Why this priority**: les bus ne sont pas les seuls véhicules lourds ; l'effet est fondé sur
une mesure pour ne pas introduire de biais (décision du mainteneur du 2026-09-29), quitte à
ne couvrir que les voies comptées.

**Independent Test**: sur une commune dont des voies sont comptées, vérifier que, à trafic bus
égal, un point sur une voie à fort trafic poids lourds compté reçoit un effet plus fort, et
qu'un point sans comptage reçoit un effet neutre « non évalué ».

**Acceptance Scenarios**:

1. **Given** deux points de même charge bus sur deux voies comptées, l'une à fort trafic
   poids lourds, l'autre à faible trafic, **When** le rapport est généré, **Then** le
   premier reçoit un effet plus fort, expliqué dans sa fiche avec la source et l'année du
   comptage.
2. **Given** un point sur une voie sans comptage publié, **When** le rapport est généré,
   **Then** l'effet est neutre et marqué « non évalué (aucun comptage publié) », quel que soit
   le type de route.
3. **Given** la synthèse du rapport, **When** elle est affichée, **Then** elle indique la
   part des points couverts par un comptage.

---

### User Story 4 - Comprendre ce qui change entre les versions (Priority: P2)

Le demandeur qui connaît le rapport v1 d'une commune voit, dans le rapport v2, pour chaque
point qui change de niveau, l'ancien niveau et la raison principale du changement. Le
mainteneur dispose d'un bilan des changements par commune avant la mise en service.

**Why this priority**: sans explication, un changement de niveau ressemble à une erreur ; le
principe IV impose que chaque écart soit expliqué.

**Independent Test**: générer Courbevoie en v1 et en v2 : chaque point qui change de niveau
porte l'ancien niveau et la raison principale.

**Acceptance Scenarios**:

1. **Given** un point passé de Sérieux à Critique, **When** le demandeur ouvre sa fiche,
   **Then** il voit « v1 : Sérieux » et la raison principale (par exemple « chaleur :
   minéralisation forte »).
2. **Given** la mise en service envisagée, **When** le mainteneur consulte le bilan de
   validation, **Then** il voit, pour les communes de référence, les changements de niveau
   et les résultats de la validation.
3. **Given** un point dont un relevé terrain de source « constatée » indique une réfection en
   2020, sans orniérage constaté depuis, **When** le rapport d'été de référence 2026 est
   consulté, **Then** son classement estimé est inchangé, il recule dans le classement
   corrigé par le terrain (effet ×0,8, six ans après les travaux), et sa fiche indique
   « réfection de 2020 (constatée) : ×0,8 » (FR-016, FR-017).

---

### Edge Cases

- Données mesurées de hauteur absentes ou incomplètes sur une zone : repli sur la méthode
  précédente pour ce point, signalé « ensoleillement estimé (données de hauteur
  incomplètes) ».
- Été de référence indisponible (données satellite couvertes de nuages) : utilisation de
  l'été précédent disponible, indiqué dans le rapport.
- Point sous un ouvrage : l'ouvrage reste pris en compte avec sa hauteur mesurée (issue #18
  non régressée).
- Commune en limite de région : indicateurs disponibles de part et d'autre, sinon repli
  signalé.
- Réfection confirmée puis orniérage « marqué » ou « grave » constaté après les travaux :
  l'effet de la réfection est annulé, la fiche l'indique (FR-018).
- Réfection seulement estimée (agent, photos aériennes, IA) : affichée comme indice, sans
  effet sur le score (FR-016).
- Indicateur de chaleur absent pour un point : effet neutre, marqué « non évalué », sans
  bloquer le rapport.

## Requirements *(mandatory)*

### Functional Requirements

**Ensoleillement**

- **FR-001**: L'ensoleillement DOIT être calculé à partir des hauteurs mesurées du bâti, de la
  végétation et des ouvrages, avec le relief, à une résolution d'environ un mètre.
- **FR-002**: L'ensoleillement DOIT couvrir la période chaude (juin à août, heure par heure
  de jour), et non un seul jour.
- **FR-003**: L'ensoleillement DOIT être mesuré sur la chaussée : zone d'arrêt pour un arrêt
  (méthode 1.2), zone de roulement pour un carrefour ou un giratoire.
- **FR-004**: La fiche DOIT indiquer les heures de soleil et la cause principale d'ombre.

**Chaleur**

- **FR-005**: Les indicateurs candidats de chaleur DOIVENT être évalués un par un : température
  de surface mesurée l'été, minéralisation autour du point, contexte urbain, chaleur rejetée
  par les climatiseurs, exposition aux canicules de l'année, en plus de l'aléa actuel.
- **FR-006**: Un indicateur NE DOIT être intégré au score que si son apport à la prédiction
  de l'orniérage est démontré sur la référence de validation (FR-013) ; les indicateurs
  écartés sont documentés avec la raison.
- **FR-007**: Les indicateurs qui changent chaque été DOIVENT être mis à jour une fois par
  an ; le rapport indique l'été de référence, et un nouvel été rend les rapports précédents
  non réutilisables (nouvelle empreinte).
- **FR-008**: Les données climatiques observées (étés, canicules) DOIVENT être partagées avec
  la projection de 007, sans double acquisition.

**Type de route**

- **FR-009**: Le trafic poids lourds hors bus DOIT intervenir dans le score par un effet
  borné, fondé **uniquement sur des comptages publiés en données ouvertes** pour la voie du
  point, affiché et expliqué dans la fiche (source, année, valeur) ; aucun forfait par type de
  route (décision du mainteneur du 2026-09-29).
- **FR-010**: Un point sans comptage publié DOIT recevoir un effet neutre, marqué « non évalué
  (aucun comptage publié) » ; la synthèse indique la part des points couverts.

**Réfection confirmée** (décision du mainteneur du 2026-09-30, cas de l'arrêt A36862
« Hérold - Mairie de Courbevoie », classé premier alors que la rue a été refaite en 2018–2021)

- **FR-016**: Une réfection confirmée DOIT pouvoir faire descendre un point dans un
  **classement corrigé par le terrain**, affiché à côté du classement estimé ; le score
  estimé n'est jamais modifié par un relevé (constitution, principe VI). Est « confirmée » seulement une année de réfection
  portée par un **relevé terrain de 003** dont la source est « constatée » ou « services
  techniques » ; une année « estimée par l'agent », un réaménagement visible sur les photos
  aériennes ou l'âge de l'enrobé estimé par IA restent des indices affichés, sans effet sur
  le score.
- **FR-017**: L'effet d'une réfection confirmée DOIT être **dégressif** : ×0,5 l'année des
  travaux (comme une chaussée en dalle béton), puis se rapprochant régulièrement de ×1,0,
  atteint 10 ans après (×0,55 après un an, ×0,75 après cinq ans) ; au-delà,
  la réfection n'a plus d'effet sur le score (elle reste affichée). La fiche indique l'année,
  la source et l'effet appliqué.
- **FR-018**: L'effet d'une réfection confirmée DOIT être annulé si le relevé le plus récent
  du point, postérieur aux travaux, constate un orniérage « marqué » ou « grave » : la fiche
  indique « réfection sans effet : orniérage constaté après les travaux ».

**Transparence et validation**

- **FR-011**: La méthode v2 DOIT porter un nouveau numéro de version majeur et une entrée
  détaillée dans le journal des changements de méthode.
- **FR-012**: Le rapport v2 DOIT indiquer, pour chaque point qui change de niveau par rapport
  à la dernière version 1.x, l'ancien niveau et la raison principale du changement.
- **FR-013**: Avant sa mise en service, la méthode v2 DOIT être validée sur les **relevés
  terrain de 003** (décision du mainteneur du 2026-09-29) : au moins 100 points relevés, dans
  au moins 3 communes, avec un niveau d'orniérage constaté ; un point est « réellement
  orniéré » si son niveau constaté est « marqué » ou « grave ». La mise en service de 004
  attend donc celle de 003 et cette campagne de relevés.
- **FR-014**: La méthode v2 NE DOIT utiliser que des données ouvertes, sans coût
  d'acquisition ; toute source hébergée hors de l'UE est déclarée dans le rapport
  (constitution, principe III).
- **FR-015**: La méthode v2 DOIT rester déterministe et reproductible : même commune, mêmes
  données, même version ⇒ même rapport au point près (constitution, principe IV).

### Key Entities *(include if feature involves data)*

- **Modèle de hauteur** : hauteurs mesurées du sol, du bâti, de la végétation et des
  ouvrages autour d'un point ; date d'acquisition.
- **Été de référence** : été dont les mesures de chaleur (température de surface, canicules)
  alimentent le score ; identifié par son année.
- **Indicateur de chaleur** : grandeur candidate, sa source, sa couverture, son apport mesuré
  à la prédiction, sa décision (retenu ou écarté) et la raison.
- **Référence de validation** : points relevés (003) avec leur niveau constaté, servant à
  comparer la v1 et la v2 (FR-013).
- **Comptage poids lourds** : trafic de poids lourds mesuré sur un tronçon de voie ; source,
  année, valeur ; rattaché aux points proches.
- **Changement de niveau** : pour un point, niveau v1, niveau v2 et raison principale.
- **Réfection confirmée** : pour un point, année de réfection issue d'un relevé terrain de 003
  de source « constatée » ou « services techniques » (FR-016).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur les points relevés de la référence de validation (FR-013), la v2 classe
  davantage de points réellement orniérés (constat « marqué » ou « grave ») dans les trois
  niveaux prioritaires (Critique, Sérieux, Important) que la v1 : au moins +10 points de
  pourcentage.
- **SC-002**: Sur un échantillon de 30 points à ensoleillement observé, l'écart moyen entre
  heures calculées et observées est inférieur à 1,5 h par jour.
- **SC-003**: Le facteur chaleur v2 distingue réellement les points : l'écart entre les 10 %
  les plus exposés et les 10 % les moins exposés d'une commune est au moins trois fois celui
  de la v1.
- **SC-004**: 100 % des points qui changent de niveau entre v1 et v2 affichent l'ancien niveau
  et une raison principale.
- **SC-005**: Un rapport v2 d'une commune comme Courbevoie est produit en moins du double du
  temps d'un rapport v1, sans coût de données supplémentaire.
- **SC-006**: Deux générations d'un même rapport v2 avec les mêmes données donnent un
  résultat identique au point près (100 % des points).

## Assumptions

- Les données de hauteur mesurées (bâti, végétation, ouvrages, relief) sont disponibles
  ouvertement, à résolution métrique, sur l'Île-de-France.
- Des mesures satellite de température de surface l'été sont disponibles ouvertement, à une
  résolution suffisante pour distinguer une place d'une rue arborée ; leur année est
  indiquée.
- L'indicateur « climatiseurs » peut ne pas exister en données ouvertes exploitables ; il est
  alors écarté et documenté (FR-006).
- Les données climatiques observées (étés, canicules) sont celles de Météo-France, sous
  licence ouverte, communes avec 007.
- La v2 remplace la v1 pour tous les nouveaux rapports ; les rapports v1 déjà produits restent
  consultables jusqu'à leur expiration (30 jours, 002 FR-008).
- La non-régression face au prototype (002, SC-003) cesse d'être un critère d'acceptation :
  la v2 s'en écarte volontairement ; elle est remplacée par la référence de FR-013.
- L'âge de l'enrobé par IA (002) et les sous-groupes Critique / Sérieux / Important (1.1)
  sont conservés tels quels.
- **Dépendance** : 004 peut être développée avant 003, mais sa mise en service exige 003 en
  service et une campagne d'au moins 100 relevés dans 3 communes (FR-013).
- Les comptages de poids lourds publiés en données ouvertes couvrent surtout le réseau
  national et départemental, selon les départements ; les voies communales sont rarement
  comptées et resteront le plus souvent « non évalué ».
