# Journal des changements de méthode

Constitution, principe IV : toute modification d'un facteur, d'une pondération, d'un seuil
ou d'une règle de priorité incrémente la version de méthode (`bitumap.score.methode`) et est
décrite ici. La version entre dans l'empreinte des rapports : un rapport produit avec une
autre version n'est jamais réutilisé.

## 2.0 — en préparation (004, non mise en service)

Appliquée seulement si `BITUMAP_METHODE=2.0` ; la **1.2 reste la méthode en service**. Mise en
service après validation sur les relevés de terrain de 003 (au moins 100 points dans 3
communes, outil `python -m bitumap.methode.evaluer`, SC-001) et décision du mainteneur. La
version et l'**été de référence** entrent dans l'empreinte : un nouvel été rend les rapports
précédents non réutilisables.

- **Ensoleillement sur hauteurs mesurées** (US1) : MNS et MNT du LiDAR HD de l'IGN autour du
  point (carré de 200 m à 1 m) ; soleil de juin à août (1er et 15 de chaque mois, 8 h 30 à
  19 h 30) ; arrêt : zone d'arrêt de la 1.2 (12 m) ; carrefour et giratoire : 5 points sur les
  voies bus à moins de 10 m. Objets fins effacés (véhicules, mâts : ouverture de 3 m, sursol
  de moins de 4 m ramené au sol, LL-016) ; houppiers d'un survol d'hiver comblés par
  l'infrarouge. **Cause principale d'ombre** affichée (bâtiment, arbre, ouvrage, relief).
  Même effet que la 1.2 (×0,8 à ×1,2 sur 0 à 12 h). Dalle absente : repli 1.2 pour le point,
  « ensoleillement estimé ».
- **Chaleur : indicateurs candidats** (US2, FR-005, FR-006) : aléa de jour (Institut Paris
  Region, référence de la 1.2), température de surface de l'été (médiane Landsat 8-9 à 30 m,
  scènes dégagées sur au moins la moitié de l'emprise ; été précédent si aucune), surfaces
  minérales à moins de 50 m (infrarouge), contexte urbain (zone climatique locale). Bornes
  fixées d'avance, ×0,92 à ×1,08 chacune. **Aucun n'agit sur le score** tant que son apport
  n'est pas démontré (`INDICATEURS_CHALEUR_RETENUS` vide) : affichés « non retenu », effet
  1,0. En conséquence, la 2.0 n'a aujourd'hui aucun effet de chaleur, contrairement à la 1.2.
- **Été de référence** : jours à 30 °C ou plus et à 35 °C ou plus à la station de référence
  (Paris-Montsouris par défaut), affichés ; jamais un facteur de classement (identiques pour
  tous les points d'une commune).
- **Poids lourds hors bus** (US3, FR-009, FR-010) : comptage publié de la voie du point (même
  numéro ou nom, à moins de 30 m), sens le plus chargé, bus du sens retirés ; effet ×1,0
  (50 PL/j) à ×1,25 (2 000 PL/j), linéaire en logarithme. Sans comptage : ×1,0, « non évalué
  (aucun comptage publié) », quel que soit le type de route ; part des points couverts dans la
  synthèse. Sources déclarées dans `src/bitumap/sources/comptages.toml`.
- **Changements de niveau expliqués** (US4, FR-011, SC-004) : la commune est aussi calculée en
  1.2 sur les mêmes données et les mêmes réponses d'IA ; un point qui change de niveau affiche
  son niveau 1.2 et le facteur dont l'effet a le plus varié ; tableau v1 × v2.
- **Classement corrigé par le terrain** (US4, FR-016 à FR-018) : couche distincte, calculée
  par l'API au service du rapport ; réfection confirmée (constatée ou services techniques) :
  ×0,5 l'année des travaux, puis retour linéaire à ×1,0 en 10 ans ; annulée si un orniérage
  marqué ou grave est constaté après les travaux. Le score estimé n'est jamais modifié
  (principe VI) ; la liste affiche l'estimé par défaut.

### Sources ajoutées

| Source | Licence | Remarque |
|---|---|---|
| IGN LiDAR HD (MNS, MNT), service raster de la Géoplateforme | Licence Ouverte Etalab 2.0 | millésime affiché (Courbevoie : survol de mars 2023) |
| USGS Landsat Collection 2 niveau 2, via Microsoft Planetary Computer | domaine public | **service hors UE déclaré** dans le rapport ; seule l'emprise de la commune est transmise |
| Météo-France, données quotidiennes (data.gouv.fr) | Licence Ouverte 2.0 | partagées avec 007 |
| Comptages routiers des Hauts-de-Seine (data.iledefrance.fr) | Licence Ouverte | % de poids lourds par sens depuis 2014 |
| Trafic moyen journalier du réseau routier national (data.gouv.fr) | Licence Ouverte | dernier millésime seulement (2024 : autoroutes concédées) |

### Indicateurs de chaleur

| Indicateur | Décision | Raison |
|---|---|---|
| Aléa de jour, température de surface, minéralisation, contexte urbain | **à évaluer** | décision après validation sur les relevés (FR-006) |
| Chaleur rejetée par les climatiseurs | **écarté** dès la 2.0 | diagnostics énergétiques : 2,3 % des bâtiments de Courbevoie renseignés, bureaux absents (research R4, décision du mainteneur du 2026-09-30) ; à réexaminer si une source couvre le tertiaire |

### Limites connues

- Poids lourds : seuls le 92 et les autoroutes concédées publient des comptages exploitables ;
  le réseau national non concédé (dernier millésime 2019, % de poids lourds fautif, LL-018)
  reste « non évalué ».
- SC-003 (écart de chaleur au moins trois fois celui de la v1) est inatteignable par un seul
  indicateur borné comme l'aléa (écart plafonné à 17,4 %) : à trancher avant la validation.
- Réfection confirmée : à Courbevoie, une réfection de 2020 (×0,8) fait passer « Hérold » du
  rang 1 au rang 11 sans le faire sortir des Critiques.
- Bornes des indicateurs et des poids lourds provisoires, à recalibrer sur les relevés (R7).

## 1.2 — 2026-09-29

- **Ponts et passerelles dans l'ensoleillement** (issue #18) : les tabliers des ouvrages
  OpenStreetMap (`bridge=*` portant une voie ferrée, une route ou un cheminement) deviennent
  des obstacles de la grille d'ombres : emprise = ligne élargie (`width`, sinon 5 m par voie
  ferrée, 8 m pour une route, 3 m pour une passerelle), hauteur 6 m par niveau (`layer`).
  Exclus : la voie du bus elle-même et, quand le bus roule sur un pont, le tablier qui le
  porte (le facteur « ouvrage d'art » est inchangé).
- **Zone d'arrêt** : l'ensoleillement d'un arrêt est la moyenne de 5 points sur les 12 m de
  chaussée où le bus s'arrête, en amont du poteau dans le sens de circulation (6 m de part et
  d'autre sur une voie à double sens) ; carrefours et giratoires : un point, inchangé.
  Raison : le poteau de « Verdun - Rue Latérale » est au bord du pont ferroviaire, le bus
  s'arrête dessous (7,5 h mesurées au poteau, 1,5 h sur la zone d'arrêt).
- **Effet à Courbevoie** : 6 arrêts sous un ouvrage ; 16 points sur 154 changent de niveau ;
  « Verdun - Rue Latérale » passe de Critique (rang 4) à À surveiller (rang 63).
  Non-régression SC-003 inchangée à 74 % (23/31) : trois P1 du prototype retrouvés, trois
  écartés parce qu'ils sont sous un pont (le prototype ignorait les ouvrages).
- **Limites** : hauteur forfaitaire des tabliers ; zone d'arrêt tracée en ligne droite le long
  de la voie ; sens de circulation déduit du sens de numérisation OSM (une voie `oneway=-1`
  serait mesurée en aval).

## 1.1 — 2026-09-29

- **Sous-groupes du P1** : les P1 (toujours 20 % des points) sont découpés par rang final,
  après l'âge de l'enrobé, en trois tiers **P1a**, **P1b**, **P1c** ; le reste de la division
  va aux premiers tiers (31 P1 ⇒ 11, 10, 10). Affichés dans la synthèse, la liste, la fiche et
  la carte (points plus gros pour P1a), filtrables.
- **Libellés affichés** (codes internes inchangés) : P1a **Critique**, P1b **Sérieux**,
  P1c **Important**, P2 **À surveiller**, P3 **Supportable**.
- **Raison** : à Courbevoie, 31 points P1 sur 154 n'aidaient pas à choisir par où commencer
  (retour du mainteneur).
- **Sans effet** sur les scores, les rangs, les priorités P1 / P2 / P3, le périmètre de l'IA
  (P1) ni la non-régression SC-003.

## 1.0 — 2026-09-28

- **Score** = produit des effets des facteurs, affiché de 0 à 100 relativement au maximum de
  la commune ; tri déterministe (score décroissant, puis identifiant).
- **Facteurs et effets** :
  - charge : ln(1 + bus/jour) ; carrefour : voie la plus chargée + moitié de la seconde ;
  - sollicitation : arrêt ×1,0, carrefour à feux ×0,8, giratoire ×0,7 ; arrêt à moins de
    40 m d'un feu ×1,2 ; 20 bus/h ou plus en pointe ×1,1 ;
  - site : pente ≥ 3 % jusqu'à ×1,32 ; béton ou pavés ×0,5 ;
  - ensoleillement de la chaussée (8 h–20 h, mi-juillet) : ×0,8 à ×1,2 ;
  - îlot de chaleur, aléa de jour 0–16 : ×0,92 à ×1,08 ;
  - âge de l'enrobé (IA, P1 seulement, « à confirmer ») : 5–12 ans ×0,85 ; plus de 12 ans
    ×1,05.
- **Priorités par rang** : P1 = 20 % premiers, P2 = 40 % suivants, P3 = le reste.
- **Écart assumé avec le prototype** : les priorités sont **figées avant** l'âge de
  l'enrobé, qui ne réordonne les points qu'à l'intérieur des P1 ; le prototype faisait
  descendre certains P1 en P2 (principe V : l'IA ne décide pas seule).
- **Limites connues** : ensoleillement estimé en un point, arbres de hauteur forfaitaire,
  sans relief ; îlots de chaleur : indicateur de jour de 2022 ; facteur chaleur peu
  discriminant (0,92–1,07 à Courbevoie). À approfondir en 004 (exposition climatique
  annuelle, minéralisation, climatiseurs, température de surface).
- **Non-régression** : 74 % des P1 du prototype retrouvés à Courbevoie (SC-003, écart
  accepté par le mainteneur le 2026-09-28).
