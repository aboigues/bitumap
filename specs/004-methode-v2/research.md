# Recherche : Méthode v2 (004)

Sources vérifiées en ligne le 2026-09-29. Chaque décision résout une inconnue du plan.

## R1. Hauteurs mesurées : MNS et MNH LiDAR HD de l'IGN

- **Décision** : l'ensoleillement v2 lit le **MNS LiDAR HD** (altitude de tout ce qui est
  au-dessus du sol : bâtiments, végétation, ouvrages d'art) et le **MNT LiDAR HD** (sol), en
  dalles de 1 km à 50 cm, rééchantillonnés à 1 m ; hauteur d'obstacle = MNS − altitude du sol
  au point de mesure, ce qui intègre le **relief**. Dalles mises en cache (bucket de cache),
  millésime dans l'empreinte.
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
    `date_edition`. Millésime retenu pour l'empreinte : `code_mission` + `date_edition`.
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

## R4. Autres candidats chaleur

| Candidat | Donnée | Décision |
|---|---|---|
| Minéralisation | part de surfaces non végétales dans 50 m : infrarouge IGN (déjà lu en 1.x) + emprises BD TOPO | évaluer (FR-005) |
| Contexte urbain | zone climatique locale de l'Institut Paris Region (déjà lue) | évaluer |
| Aléa actuel | aléa de jour IPR (déjà lu) | référence v1, évaluée comme les autres |
| Climatiseurs | DPE de l'ADEME : équipement de refroidissement ([logements existants](https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021), [tertiaire](https://data.ademe.fr/datasets/dpe-tertiaire)), rattachés aux bâtiments ; surface refroidie dans 100 m | évaluer ; **écarter si** la couverture est insuffisante (moins d'un bâtiment sur cinq diagnostiqué dans la zone) — documenté (FR-006) |
| Canicules de l'été | jours de forte chaleur à la station Météo-France de référence (données quotidiennes, Licence Ouverte, partagées avec 007) | **pas un facteur de classement** : identique pour tous les points d'une commune, il ne change aucun rang (le score est relatif au maximum de la commune) ; il est affiché comme **été de référence** et sert à 007 |

- **Mesuré au développement (T004, T005, 2026-09-30)** :
  - **Climatiseurs (DPE)** : le jeu `dpe03existant` de l'ADEME (Licence Ouverte) porte
    `surface_climatisee`, `type_generateur_froid`, `id_rnb` et des coordonnées ; le jeu
    tertiaire `dpe01tertiaire` n'a **aucun champ de refroidissement**. À Courbevoie :
    24 439 DPE de logements, dont **374 avec une surface climatisée** (1,5 %), soit
    **117 bâtiments** sur environ 5 100 (2,3 %), tous résidentiels ; les bureaux (La
    Défense) sont absents. Couverture très inférieure au seuil de R4 (un bâtiment sur
    cinq) et biaisée : **recommandation : écarter l'indicateur dès maintenant** (FR-006,
    raison documentée), ce qui supprime T025 et le candidat `chaleur_climatiseurs` —
    **décision du mainteneur requise**.
  - **Météo-France** : jeu « Données climatologiques de base quotidiennes » (Licence
    Ouverte 2.0), fichiers par département sans compte, hébergés en France (OVH) :
    `Q_75_latest-2025-2026_RR-T-Vent.csv.gz`, mis à jour chaque jour. Station de
    référence proposée : **Paris-Montsouris (`75114001`)**. Été 2026 : 92 jours complets,
    **39 jours à 30 °C ou plus, 20 à 35 °C ou plus, maximum 40,6 °C**. 007 prévoit le même
    module `sources/meteo.py` : écrit une seule fois.

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

## R6. Explication des changements de niveau

- **Décision** : au cours du même lot, le point est aussi calculé en **méthode 1.2**
  (réutilisant les réponses d'IA en cache : aucun coût d'IA supplémentaire) ; la raison
  principale d'un changement de niveau est le facteur dont l'effet a le plus varié (en
  logarithme). Stocké dans le rapport (`niveau_v1`, `raison_changement`).
- **Alternative écartée** : relire le dernier rapport 1.x de la commune (souvent absent ou
  expiré).

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

## R8. Version, empreinte, reproductibilité

- **Décision** : `VERSION_METHODE = "2.0"` ; nouvelles sources versionnées dans l'empreinte :
  millésime LiDAR des dalles, été de référence (température de surface), année des
  comptages, date d'extraction des DPE. Un nouvel été rend les rapports précédents non
  réutilisables (FR-007). Déterminisme : dalles et scènes figées par identifiant, médianes
  et tris stables (SC-006).
- **Non-régression (constitution, principe VII)** : le cas Courbevoie reste un test de
  non-régression, adapté à la v2 : le seuil de 74 % de P1 du prototype (002 SC-003) cesse de
  s'appliquer, mais **chaque changement de niveau entre 1.2 et 2.0 doit porter sa raison**
  (`raison_changement`, R6), ce qui satisfait « tout écart de rang doit être expliqué par un
  changement de méthode ou de source ». Il vérifie aussi la stabilité (même entrée ⇒ même
  sortie) et l'issue #18 (Verdun - Rue Latérale sous le pont).
