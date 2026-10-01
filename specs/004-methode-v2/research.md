# Recherche : Méthode v2 (004)

Sources vérifiées en ligne le 2026-09-29. Chaque décision résout une inconnue du plan.

## R1. Hauteurs mesurées : MNS et MNH LiDAR HD de l'IGN

- **Décision** : l'ensoleillement v2 lit le **MNS LiDAR HD** (altitude de tout ce qui est
  au-dessus du sol : bâtiments, végétation, ouvrages d'art) et le **MNT LiDAR HD** (sol), en
  dalles de 1 km à 50 cm, rééchantillonnés à 1 m ; hauteur d'obstacle = MNS − altitude du sol
  au point de mesure, ce qui intègre le **relief**. Dalles mises en cache (bucket de cache),
  millésime inscrit dans le rapport (R8).
- **Source** : [MNS LiDAR HD](https://www.data.gouv.fr/datasets/mns-lidar-hd), [MNH LiDAR
  HD](https://www.data.gouv.fr/datasets/mnh-lidar-hd) ; Licence Ouverte ; dalles GeoTIFF
  téléchargeables sur cartes.gouv.fr, Île-de-France disponible ([IGN, premiers
  modèles](https://cartes.gouv.fr/aide/fr/partenaires/ign/generalites-ign/actualites/2025-03-lidarhd-et-produits-derives/)).
- **Raison** : remplace les trois approximations de la 1.2 (hauteur de bâtiment BD TOPO,
  arbres à 8 m forfaitaires, tabliers à 6 m) par la mesure ; résout la limite « pas de
  relief ».
- **Repli** (cas limite de la spec) : dalle absente ⇒ méthode 1.2 pour ce point, signalée.
- **À mesurer au développement** : volume par commune (≈ 10 à 20 dalles pour Courbevoie),
  temps de lecture ; mode d'accès par programme (téléchargement de dalles ou service raster
  de la Géoplateforme).

- **Mesuré au développement (T001, 2026-09-30)** :
  - **Accès** : service raster de la Géoplateforme, sans clé ni compte :
    `https://data.geopf.fr/wms-r/wms`, `GetMap`, couches
    `IGNF_LIDAR-HD_{MNS|MNT|MNH}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93`, style `normal`,
    `FORMAT=image/geotiff` : altitudes réelles en `float32`, 50 cm, EPSG:2154, nodata −9999.
    Le **MNH** (hauteur au-dessus du sol) est servi directement.
  - **Index des dalles et millésime** : couche vecteur `IGNF_LIDAR-HD_METADONNEE:metadata`
    (`https://data.geopf.fr/wfs/ows`) : dalle de 1 km (`coordonnees_nw`), URL des trois
    modèles, `code_mission`, `date_debut_acquisition`, `date_fin_acquisition`,
    `date_edition`. Millésime affiché dans le rapport : `code_mission` + `date_fin_acquisition` (R8) ; la date du relevé dit au lecteur si les arbres avaient leurs feuilles.
  - **Volume** : Courbevoie = 16 dalles, toutes de la mission `22LHDKE` (édition
    2025-06-06). Une dalle complète pèse 15,6 Mo par modèle (1,8 s) ; la commune entière,
    environ 750 Mo pour trois modèles. **Décision** : extraction **par point**, comme la
    végétation de 1.x (`VEGETATION_DEMI_COTE_M = 100`) : carré de 200 m à 1 m, MNS et MNT,
    160 Ko par modèle et par point, environ 0,8 s par requête. Le protocole `Fournisseur`
    expose donc `hauteurs(lon, lat)` et non `hauteurs(emprise)` (T009, T016 ajustées).
  - **⚠️ Acquisition hivernale** : Courbevoie a été survolée les **2 et 3 mars 2023**,
    arbres sans feuilles. Le MNS sous-estime donc le houppier des arbres caducs, qui font
    l'ombre l'été. **Parade** (T017, T018) : un pixel dont la hauteur MNH dépasse 2 m et que
    l'infrarouge (déjà lu en 1.x) classe en végétation est traité comme **opaque** à sa
    hauteur MNH ; à vérifier sur les points arborés de SC-002.

## R2. Période chaude et cause d'ombre

- **Décision** : positions du soleil **heure par heure** sur 6 jours représentatifs (1er et 15
  de juin, juillet, août), de 8 h à 20 h ; heures de soleil = moyenne sur ces jours.
  Zone de mesure : zone d'arrêt (1.2) pour un arrêt ; pour un carrefour ou un giratoire,
  5 points sur les voies bus à moins de 10 m du centre.
- **Cause principale d'ombre** : l'obstacle qui bloque le plus de rayons est classé
  « bâtiment » (dans une emprise BD TOPO), « ouvrage » (sous un tablier OSM), « arbre »
  (hauteur MNH > 2 m et végétation sur l'infrarouge) ou « relief » (sinon).
- **Raison** : 6 jours × 13 heures suffisent à représenter la saison (la course du soleil
  varie lentement) pour un coût borné (SC-005).
- **Précisé au développement (US1, 2026-09-30), sur les 154 points de Courbevoie** :
  - **Instants** : 12 instants horaires centrés (8 h 30 à 19 h 30) par jour, soit 1 h de
    soleil par instant dégagé et 12 h au plus, comme la 1.2 (même effet borné).
  - **Hauteur de référence** : sol (MNT) au point de mesure, ou dessus du tablier (MNS) si
    le bus roule sur un pont.
  - **Artefacts du MNS écartés** (constatés, images à l'appui) : les **véhicules présents
    lors du survol** (2 à 3 m au bord des points de mesure) et les **objets fins** (mâts de
    feux, lampadaires : « obstacles » de 8 à 16 m à 2 m des feux) cachaient le soleil à tort.
    Le sursol est ouvert morphologiquement (3 × 3 m : objets de moins de 3 m de large
    effacés) puis ramené au sol en dessous de 4 m.
  - **Houppier d'hiver** : dans les cellules de végétation (infrarouge), trous comblés par la
    hauteur maximale voisine (5 × 5 m).
  - **Cause « arbre »** : végétation de l'infrarouge à 1 m près, **ou** sursol rugueux (plus
    de 2 m d'écart entre cellules de sursol sur 5 × 5 m) : l'infrarouge manque les arbres à
    l'ombre des immeubles (avenue Gambetta). Emprises BD TOPO élargies d'un mètre pour le
    classement (calage des toits). Limite : une passerelle non répertoriée dans OSM (La
    Défense, avenue de la Division Leclerc) est classée « arbre » ; l'ombre, elle, est juste.
  - **Résultats** : 154/154 points mesurés au LiDAR ; causes : bâtiments 97, arbres 51,
    ouvrages 5, relief 1 ; écart moyen à la 1.2 : −0,7 h/jour ; 30 points changent de
    niveau ; A27418 (issue #18) à 0,2 h, cause « ouvrage » ; calcul 1,45 fois plus long que
    la 1.2 hors téléchargement (le LiDAR ajoute environ 250 s par commune en ligne,
    2 requêtes par point, pas de cache) ; déterministe.

## R3. Température de surface l'été (candidat chaleur n° 1)

- **Constat** : les produits Landsat 8-9 de niveau 2 « Surface Temperature » (30 m, bande
  thermique à 100 m) sont distribués par l'USGS ([Landsat Collection 2 Level-2](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products)) ;
  le [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/news/2026-1-16-landsat-8-and-landsat-9-collection-2-level-1-data-availability-copernicus-data-space)
  ne met en miroir que le **niveau 1** (température à recalculer).
- **Décision** : médiane de la température de surface des scènes sans nuage de juin à août
  de l'**été de référence**, au point (fenêtre de 30 m) ; source USGS, données du domaine
  public, **service hors UE déclaré** dans le rapport (principe III : seule une emprise
  géographique est transmise, aucune donnée personnelle). Été sans scène exploitable ⇒ été
  précédent, indiqué.
- **Alternatives écartées** : Sentinel-3 (1 km, ne distingue pas une place d'une rue) ;
  recalcul depuis le niveau 1 sur CDSE (émissivité, atmosphère : complexité non justifiée
  tant que l'apport n'est pas démontré, FR-006).

- **Mesuré au développement (T002, 2026-09-30)** :
  - **Recherche** : le service STAC de l'USGS
    (`https://landsatlook.usgs.gov/stac-server`, collection `landsat-c2l2-st`) répond sans
    compte : 11 scènes pour l'été 2026 sur Courbevoie, dont 3 exploitables (13 juin, 8 et
    16 août, moins de 30 % de nuages).
  - **Téléchargement USGS** : les fichiers redirigent vers la connexion **EROS
    (`ers.cr.usgs.gov`) : compte obligatoire**. Le miroir S3 `usgs-landsat` est en
    « requester pays » (compte AWS payant) : écarté.
  - **Copie sans compte** : Microsoft Planetary Computer (collection `landsat-c2-l2`,
    mêmes produits USGS), jeton anonyme temporaire
    (`https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2`),
    fichiers **stockés dans l'UE** (Azure West Europe, `landsateuwest`), fournisseur
    américain. Lecture d'une fenêtre sur Courbevoie : 0,4 à 1,3 s par scène.
  - **Premier résultat** : médiane de l'été 2026 sur Courbevoie (3 scènes, nuages masqués
    par `QA_PIXEL`) : 32,0 °C (10 % les plus frais) à 37,4 °C (10 % les plus chauds) ;
    l'indicateur a de quoi distinguer les points, à 30 m près.
  - **Décision du mainteneur requise** : (a) USGS avec un compte EROS gratuit (identifiant
    à stocker dans Secret Manager), ou (b) Planetary Computer sans compte, sans secret. Dans
    les deux cas, service **hors UE déclaré** (principe III : seule une emprise transmise).

- **Décision du mainteneur (2026-10-01)** : **(b) Microsoft Planetary Computer**. Le compte
  EROS a été créé le 2026-09-30, mais l'USGS n'a pas accordé l'accès MACHINE (permissions
  `user` seulement, `download-options` en 403, toujours le cas le 2026-10-01). Planetary
  Computer distribue les mêmes produits, sans compte ni secret ; identifiants USGS retirés
  (`.env.example`, `config.py`, secrets prévus dans `configuration.md`).
- **Mesuré au développement (US2, 2026-10-01)** : 10 scènes Landsat 8-9 sur Courbevoie l'été
  2026, **6 retenues** (au moins 50 % de l'emprise dégagée selon `QA_PIXEL` : nuage, cirrus,
  ombre, neige, eau masqués), lues en 4 s environ. Médiane par pixel : 29,6 °C (10 % les
  plus frais) à 35,5 °C (10 % les plus chauds) ; plus basse que la première mesure (3 scènes
  très dégagées) parce que des journées plus fraîches (23 juillet) entrent dans la médiane,
  l'écart entre zones restant de l'ordre de 6 °C. Aux points : 27,3 à 38,0 °C (fenêtre de
  30 m sur la chaussée). Grille Lambert 93 de 30 m : 40 ko figés.

## R4. Autres candidats chaleur

| Candidat | Donnée | Décision |
|---|---|---|
| Minéralisation | part de surfaces non végétales dans 50 m : infrarouge IGN (déjà lu en 1.x) + emprises BD TOPO | évaluer (FR-005) |
| Contexte urbain | zone climatique locale de l'Institut Paris Region (déjà lue) | évaluer |
| Aléa actuel | aléa de jour IPR (déjà lu) | référence v1, évaluée comme les autres |
| Climatiseurs | DPE de l'ADEME : équipement de refroidissement ([logements existants](https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021), [tertiaire](https://data.ademe.fr/datasets/dpe-tertiaire)), rattachés aux bâtiments ; surface refroidie dans 100 m | **écarté de la 2.0** (couverture de 2,3 % à Courbevoie, logements seulement, ci-dessous ; décision du mainteneur du 2026-09-30) ; à réexaminer si un jeu couvrant le tertiaire devient disponible |
| Canicules de l'été | jours de forte chaleur à la station Météo-France de référence (données quotidiennes, Licence Ouverte, partagées avec 007) | **pas un facteur de classement** : identique pour tous les points d'une commune, il ne change aucun rang (le score est relatif au maximum de la commune) ; il est affiché comme **été de référence** et sert à 007 |

- **Mesuré au développement (T004, T005, 2026-09-30)** :
  - **Climatiseurs (DPE)** : le jeu `dpe03existant` de l'ADEME (Licence Ouverte) porte
    `surface_climatisee`, `type_generateur_froid`, `id_rnb` et des coordonnées ; le jeu
    tertiaire `dpe01tertiaire` n'a **aucun champ de refroidissement**. À Courbevoie :
    24 439 DPE de logements, dont **374 avec une surface climatisée** (1,5 %), soit
    **117 bâtiments** sur environ 5 100 (2,3 %), tous résidentiels ; les bureaux (La
    Défense) sont absents. Couverture très inférieure au seuil de R4 (un bâtiment sur
    cinq) et biaisée : **indicateur écarté de la 2.0** (FR-006, décision du mainteneur du 2026-09-30) :
    T025 sans objet, pas de candidat `chaleur_climatiseurs`. À réexaminer dans une version
    ultérieure si les DPE tertiaires ou une autre source ouverte renseignent la climatisation
    des bureaux.
  - **Météo-France** : jeu « Données climatologiques de base quotidiennes » (Licence
    Ouverte 2.0), fichiers par département sans compte, hébergés en France (OVH) :
    `Q_75_latest-2025-2026_RR-T-Vent.csv.gz`, mis à jour chaque jour. Station de
    référence proposée : **Paris-Montsouris (`75114001`)**. Été 2026 : 92 jours complets,
    **39 jours à 30 °C ou plus, 20 à 35 °C ou plus, maximum 40,6 °C**. 007 prévoit le même
    module `sources/meteo.py` : écrit une seule fois.

- **Mesuré au développement (US2, 2026-10-01)** :
  - **Indicateurs aux points de Courbevoie** : aléa 0 à 15/16 (150 points sur 154) ;
    température de surface 27,3 à 38,0 °C (154) ; surfaces minérales à 50 m 62 à 100 %
    (médiane 95 %, 154) ; contexte urbain (153) surtout bâti ouvert de hauteur moyenne (5),
    bâti compact (2, 3), bâti ouvert de grande hauteur (4), arbres épars (B).
  - **Bornes fixées d'avance** (même amplitude que l'aléa de la 1.2, ×0,92 à ×1,08) :
    température 28 °C → 38 °C ; minéralisation 0 → 100 % ; contexte : bâti compact (1, 2,
    3), grands bâtiments bas (8), industrie lourde (10), sol imperméable (E) ×1,08 ; arbres,
    végétation basse, sol nu, eau (A à D, F, G) ×0,92 ; autres ×1,0. Recalibrées sur les
    relevés (R7).
  - **SC-003 mesuré (T029, consigné)** : écart d'effet entre les 10 % de points les plus et
    les moins exposés (effet qu'aurait l'indicateur s'il était retenu) : aléa v1 12,5 % ;
    température de surface 13,6 % (×1,08 la v1) ; minéralisation 3,9 % (×0,31) ; contexte
    urbain 17,4 % (×1,39). **Le seuil de SC-003 (trois fois la v1) est inatteignable par un
    indicateur seul** avec les bornes de la v1 : l'écart est plafonné à 1,08 / 0,92 − 1 =
    17,4 %. À trancher par le mainteneur : élargir les bornes d'un indicateur retenu, mesurer
    SC-003 sur la combinaison des indicateurs retenus, ou reformuler SC-003.
  - Exemple : « Paix - Verdun » (A23742, orniérage présent mais non critique selon le
    mainteneur, 2026-10-01) a un aléa faible (3/16) mais une température de surface de
    37,1 °C, parmi les 10 % les plus chaudes : signal encourageant pour la température de
    surface, à confirmer sur les relevés (R7).

## R5. Poids lourds : comptages publiés (décision du mainteneur)

- **Sources identifiées** : comptages de la voirie départementale des
  [Hauts-de-Seine](https://data.iledefrance.fr/explore/dataset/comptages-routiers-lineaires-dans-les-hauts-de-seine/table/)
  (moyenne journalière annuelle poids lourds) ; [trafic moyen journalier annuel du réseau
  routier national](https://www.data.gouv.fr/datasets/trafic-moyen-journalier-annuel-sur-le-reseau-routier-national).
  **Couverture des sept autres départements à inventorier au développement** (tâche dédiée) ;
  un département sans comptage publié ⇒ « non évalué ».
- **Décision** : un point reçoit la valeur du tronçon compté de **sa voie** (même numéro de
  route ou même nom, à moins de 30 m) ; effet borné, fonction croissante du nombre de poids
  lourds par jour (×1,0 à ×1,25), forme et bornes calibrées sur les relevés (R7). Sans
  comptage : ×1,0, « non évalué (aucun comptage publié) ». Année du comptage affichée.
- **Biais assumé** : à trafic égal, un point compté peut être plus haut qu'un point non
  compté ; la synthèse affiche la part de points couverts (FR-010).

- **Mesuré au développement (T003, 2026-09-30) : inventaire des comptages** :

  | Département | Comptages poids lourds publiés | Détail |
  |---|---|---|
  | 92 Hauts-de-Seine | ✅ | `comptages-routiers-lineaires-dans-les-hauts-de-seine` (data.iledefrance.fr, Licence Ouverte) : 368 sections, **274 avec % poids lourds** par sens (comptages 2021–2023) ; Courbevoie : 10 sections avec poids lourds (RD7, RD908, RD993, RD6, RD9B, RD106, RD6A, RD12) |
  | Réseau national | ✅ | TMJA du réseau routier national (data.gouv.fr, Licence Ouverte), 2024 : champ `ratio_PL` ; 79 sections en Île-de-France, surtout autoroutes (peu d'arrêts de bus) |
  | 75 Paris | ❌ | comptages permanents sans distinction des poids lourds |
  | 77, 91, 95 | ❌ | cartes et plaquettes PDF seulement, aucune donnée exploitable |
  | 78, 93, 94 | ❌ | aucun jeu trouvé |

  Conséquence : hors Hauts-de-Seine, le facteur restera « non évalué » partout, sauf aux
  rares arrêts sur le réseau national. L'inventaire est à refaire à chaque été de
  référence (un département peut publier).

- **Mesuré au développement (US3, 2026-10-01)** :
  - **Réseau national** : depuis 2022, seul le réseau **concédé** est publié (2024 : 1 100
    sections en France, aucune nationale d'Île-de-France). Le dernier millésime du réseau non
    concédé (2019) a un % de poids lourds **fautif en Île-de-France** : valeurs multipliées par
    10 (N13 : 4,6 % en 2018, « 46 » en 2019 ; 76 sections au-dessus de 100 %). **Décision du
    mainteneur** : dernier millésime publié seulement ; le réseau non concédé reste « non
    évalué ». Garde-fou : tout % de poids lourds hors de ]0, 100] écarte la section. Le jeu du
    92 couvre déjà la RN13 et l'A14 à Courbevoie.
  - **Hauts-de-Seine** : poids lourds par sens = trafic du sens × % du sens ; valeur retenue =
    sens le plus chargé parmi les sens complets ; les comptages sans % de poids lourds (avant
    2014) sont écartés.
  - **Bus retirés** (décision du mainteneur) : les poids lourds comptés comprennent les bus,
    déjà comptés par la charge ; on retire les bus du sens (charge IDFM de la voie, divisée par
    deux sur une voie à double sens), avec un minimum de 0.
  - **Effet initial** (décision du mainteneur) : linéaire en logarithme des poids lourds hors
    bus du sens le plus chargé, ×1,0 à 50 PL/j (classe T3 du dimensionnement des chaussées) et
    ×1,25 à partir de 2000 PL/j (classe TS) ; recalibré sur les relevés (R7).
  - **Courbevoie** : 47 sections dans l'emprise (toutes du 92) ; 90 points sur 154 couverts
    (58 %), tous sur des départementales ; 30 points de départementales restent non évalués
    (RD9 boulevard Saint-Denis, RD6 rue de Bezons : comptages sans % de poids lourds) ; 18
    points couverts à ×1,0 (plus de bus que de poids lourds comptés au-delà de 50) ; 22 points
    sur 154 changent de priorité (7 entrent en P1, 7 en sortent).
  - **Pas de cache** : comme le LiDAR, relu à chaque rapport.
  - **Catalogue des sources** (revue de la PR #33) : les sources sont déclarées dans
    `src/bitumap/sources/comptages.toml` (jeu, champs par sens ou total des deux sens,
    licence), lues par un lecteur générique par plateforme (`opendatasoft`,
    `datagouv_shapefile`). Un département qui publie sur une de ces plateformes s'ajoute par
    une entrée du catalogue, sans code ; le fichier fait partie de la méthode (principe IV),
    toute modification passe par une PR.

## R6. Explication des changements de niveau

- **Décision** : au cours du même lot, le point est aussi calculé en **méthode 1.2**
  (réutilisant les réponses d'IA en cache : aucun coût d'IA supplémentaire) ; la raison
  principale d'un changement de niveau est le facteur dont l'effet a le plus varié (en
  logarithme). Stocké dans le rapport (`niveau_v1`, `raison_changement`).
- **Alternative écartée** : relire le dernier rapport 1.x de la commune (souvent absent ou
  expiré).
- **Mesuré au développement (US4, 2026-10-01)** : les réponses du fournisseur lues pour la
  2.0 sont gardées en mémoire (`score.comparaison.Memoire`) et resservies au calcul 1.2 ;
  l'âge de l'enrobé des points analysés en 2.0 est repris, un point P1 en 1.2 seulement reste
  « non évalué » (aucun appel d'IA ; l'âge ne change jamais la priorité). Les quatre
  indicateurs de chaleur de la 2.0 sont regroupés face à l'aléa de la 1.2 ; une variation
  d'effet sous 0,5 % est ignorée et le changement attribué au « déplacement des autres
  points ». Courbevoie : 45 points sur 154 changent de niveau, tous expliqués (poids lourds
  16, ensoleillement 16, chaleur 13) ; niveaux v1 identiques à un calcul 1.2 seul ; durée
  2.0 + comparaison = 1,5 × la 1.2 (SC-005).

## R7. Validation et choix des indicateurs sur les relevés de 003

- **Décision** : un outil d'évaluation (`python -m bitumap.methode.evaluer`), sur le modèle de
  `bitumap.ia.evaluer`, lit les relevés de 003 (au moins 100 points, 3 communes ; orniéré =
  « marqué » ou « grave ») et produit un rapport Markdown :
  1. **SC-001** : part des points orniérés dans les trois niveaux prioritaires, v1 contre v2 ;
  2. **apport de chaque indicateur** (FR-006) : même mesure avec et sans l'indicateur ; un
     indicateur est retenu s'il améliore la mesure d'au moins 2 points **et** ne la dégrade
     dans aucune commune de référence ;
  3. **calibrage** des bornes d'effet (chaleur, poids lourds) : peu de paramètres, bornes
     fixées d'avance, pour éviter le sur-ajustement sur une centaine de points.
- **Décision de mise en service** : prise par le mainteneur sur ce rapport (spec, story 4).
- **SC-002** (ensoleillement observé à ±1,5 h) : 30 points observés pendant la campagne de
  relevés (heures d'ombre notées dans l'observation) ou par photos horodatées ; protocole
  dans le quickstart.
- **Mesuré au développement (US4, 2026-10-01)** : outil `python -m bitumap.methode.evaluer`
  écrit et testé sur des relevés synthétiques ; exports GeoJSON ou CSV de 003 (plusieurs
  fichiers, un par commune, dernier relevé de chaque point) ; heures de soleil observées
  dans un CSV `point;heures` (option `--soleil`), l'export de 003 n'ayant pas de champ
  dédié ; l'âge de l'enrobé n'est pas évalué (aucun appel d'IA : il ne change pas la
  priorité, donc pas SC-001). Le calibrage des bornes (point 3) reste manuel : l'outil donne
  les mesures avec et sans chaque indicateur.

## R8. Version, empreinte, reproductibilité

- **Décision** : `VERSION_METHODE_V2 = "2.0"`, appliquée si `BITUMAP_METHODE=2.0`.
  **Précisé au développement (T010, 2026-09-30)** : l'empreinte est calculée **avant** la
  génération (réutilisation d'un rapport en cache) ; seules des versions connues à ce moment
  peuvent y entrer. En 2.0, elle reçoit donc la version de méthode et l'**été de référence**
  (réglage, ou dernier été complet à partir d'octobre) : un nouvel été rend les rapports
  précédents non réutilisables (FR-007). Le millésime LiDAR (par dalle, donc par point) et
  l'année des comptages sont traités comme la BD TOPO : **inscrits dans le rapport** (fiche
  et sources) et bornés par la validité de 30 jours d'un rapport (002 FR-008), sans entrer
  dans l'empreinte. Déterminisme : dalles et scènes figées par identifiant, médianes
  et tris stables (SC-006).
- **Non-régression (constitution, principe VII)** : le cas Courbevoie reste un test de
  non-régression, adapté à la v2 : le seuil de 74 % de P1 du prototype (002 SC-003) cesse de
  s'appliquer, mais **chaque changement de niveau entre 1.2 et 2.0 doit porter sa raison**
  (`raison_changement`, R6), ce qui satisfait « tout écart de rang doit être expliqué par un
  changement de méthode ou de source ». Il vérifie aussi la stabilité (même entrée ⇒ même
  sortie) et l'issue #18 (Verdun - Rue Latérale sous le pont).

## R9. Réfection confirmée : classement corrigé par le terrain (FR-016 à FR-018)

Clarification du 2026-09-30 (spec, session du jour) ; cas déclencheur : arrêt A36862
« Hérold - Mairie de Courbevoie », premier du classement alors que la rue a été refaite en
2018–2021.

- **Contrainte constitutionnelle** : principe VI, « les relevés … ne modifient jamais le
  calcul d'origine : ils l'enrichissent ou le **corrigent dans une couche distincte**, et le
  rapport distingue « estimé » et « constaté » ». Multiplier le score estimé par l'effet de
  la réfection violerait ce principe.
- **Décision** : le score **estimé** (méthode 2.0, produit par le job) reste inchangé. Une
  couche distincte, le **classement corrigé par le terrain**, est calculée **au moment où
  l'API sert le rapport**, comme le bloc `releves` de 003 :
  1. l'API lit `points.geojson` du rapport (facteurs et effets de chaque point) et les
     derniers relevés visibles de la commune ;
  2. pour chaque point, **réfection confirmée** = la plus récente année de réfection portée
     par un relevé visible de source `constatee` ou `services_techniques` (FR-016) ;
  3. **effet** = `0,5 + 0,05 × n`, borné à 1,0, où `n` = année de l'été de référence du
     rapport − année de réfection (≥ 0) : ×0,5 l'année des travaux, ×1,0 au bout de 10 ans
     (FR-017). L'été de référence (R8) plutôt que la date du jour : même rapport, mêmes
     relevés ⇒ même classement corrigé, quel que soit le jour de consultation (principe IV) ;
  4. **annulation** (FR-018) : si le relevé visible le plus récent du point est daté d'une
     année ≥ l'année de réfection et constate un niveau `marque` ou `grave`, effet 1,0 avec
     le motif « réfection sans effet : orniérage constaté après les travaux » ;
  5. score corrigé = score brut × effet, puis **mêmes règles de rangs et de niveaux** que le
     score estimé (`score.combinaison`, priorités figées avant l'âge de l'enrobé) : rang et
     niveau corrigés ;
  6. un bloc JSON distinct, `<script type="application/json" id="classement-terrain">`, est
     inséré après le bloc `releves` (avant le script, LL-012) : pour chaque point touché,
     effet, année, source, motif, rang et niveau corrigés ; plus le nombre de points
     touchés.
- **Affichage** (rapports 2.0 seulement ; le script des rapports 1.x l'ignore, LL-011) :
  - fiche : « Estimé : rang 1, Critique · Corrigé par le terrain : rang 57, À surveiller
    (réfection de 2020, constatée : ×0,8) », ou le motif d'annulation ;
  - liste : un choix « classement estimé / corrigé par le terrain » (estimé par défaut tant
    que la 2.0 n'est pas validée, FR-013) ;
  - synthèse : « N points corrigés par une réfection confirmée ».
- **Pourquoi au service et non dans le job** : un relevé déposé aujourd'hui agit tout de
  suite, sans régénérer le rapport ni changer son empreinte (le rapport en cache reste
  valable 30 jours) ; le calcul d'origine reste celui du job, intact (principe VI).
- **Alternatives écartées** :
  - multiplier le score estimé dans le job : viole le principe VI, et un nouveau relevé
    n'agirait qu'au rapport suivant (empreinte à étendre aux relevés) ;
  - recalcul dans le navigateur : dupliquerait en JavaScript les règles de rangs et de
    niveaux (risque d'écart avec `score.combinaison`) ;
  - amender le principe VI : inutile, la couche distincte répond à la demande.
- **Validation (FR-013)** : l'outil d'évaluation (R7) mesure SC-001 sur le classement
  **estimé** (la méthode) ; le classement corrigé est rapporté à part, pour information.
- **Données** : aucune table nouvelle ; lecture de `releve` / `releve_version` (003). Aucune
  donnée personnelle dans le bloc (ni auteur, ni adresse).
