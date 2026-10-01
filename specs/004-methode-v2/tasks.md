---
description: "Tâches d'implémentation de la méthode v2"
---

# Tasks: Méthode v2 (ensoleillement, chaleur, poids lourds)

**Input**: Documents de conception dans `/specs/004-methode-v2/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R8), data-model.md,
contracts/methode-v2.md, quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des tests sans réseau, sur données
figées ; la spec définit des critères vérifiables (SC-004, SC-005, SC-006 en développement ;
SC-001, SC-002, SC-003 à la validation). Écrire les tests de chaque story **avant** son
implémentation et vérifier qu'ils échouent.

**Organization**: tâches groupées par user story (US1 à US4 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US4

## Règles communes

- **La 1.2 reste la méthode en service** : tout le code v2 est derrière `BITUMAP_METHODE`
  (défaut `1.2`) ; aucun rapport produit en 1.2 ne change (tests existants inchangés, dont
  `tests/non_regression/test_courbevoie.py` et le test de l'issue #18).
- Aucune nouvelle dépendance Python sans vérification de la dernière version stable et
  accord du mainteneur (plan : rasterio, numpy, pandas, pvlib suffisent).
- Chaque nouvelle source : un adaptateur dans `src/bitumap/sources/`, une `Provenance`
  (nom, licence, URL, date), mise en cache dans le bucket de cache, un test sur fixture sans
  réseau (principes III et VII) ; la source USGS est marquée **hors UE**.
- Déterminisme (SC-006) : dalles et scènes identifiées, tris stables, aucun `set` itéré,
  aucune date « du jour » dans le calcul (été de référence fixé par la configuration).
- Commits sur la branche `004-methode-v2`, fichiers nommés explicitement (LL-002) ; une PR
  par étape livrable ; jamais de fusion par l'agent (principe IX).

---

## Phase 1: Setup

**Purpose**: vérifier les sources avant d'écrire le code qui en dépend (inconnues du plan).

- [X] T001 Vérifier l'accès par programme aux dalles **MNS et MNT LiDAR HD** de l'IGN pour Courbevoie (téléchargement de dalles de 1 km ou service raster de la Géoplateforme) : URL exacte, format (GeoTIFF, 50 cm), millésime, volume et temps de lecture pour la commune ; consigner le résultat dans `specs/004-methode-v2/research.md` (R1, section « Mesuré au développement »)
- [X] T002 [P] Vérifier l'accès aux scènes **Landsat Collection 2 niveau 2** (température de surface) de l'USGS pour l'été 2026 sur Courbevoie : service de recherche (STAC), authentification éventuelle (si un compte est exigé : **arrêter et demander au mainteneur**, aucun secret ajouté sans accord), masque de nuages, nombre de scènes exploitables juin–août ; consigner dans `research.md` (R3)
- [X] T003 [P] Inventorier les **comptages poids lourds publiés** des huit départements d'Île-de-France (75, 77, 78, 91, 92, 93, 94, 95) et du réseau national : jeu de données, licence, format, années, champ « poids lourds par jour », géométrie ou repère ; tableau dans `research.md` (R5) ; un département sans comptage ⇒ noté « non évalué »
- [X] T004 [P] Vérifier les **DPE de l'ADEME** (logements existants et tertiaire) : accès par commune, champ de l'équipement de refroidissement, rattachement au bâtiment (adresse, identifiant RNB ou BD TOPO), couverture à Courbevoie (part des bâtiments diagnostiqués) ; consigner dans `research.md` (R4)
- [X] T005 [P] Vérifier les **données quotidiennes de Météo-France** (température maximale, station de référence de l'agglomération parisienne), licence et accès ; si la branche `007-projection-ete` définit déjà `sources/meteo.py`, reprendre son contrat pour ne pas acquérir deux fois (FR-008) ; consigner dans `research.md` (R4)

**Checkpoint**: chaque source a un accès, une licence et un volume connus ; les écarts au plan sont documentés avant d'écrire le code.

---

## Phase 2: Foundational (prérequis de toutes les stories)

**Purpose**: sélection de méthode, champs du rapport, fournisseur de données et fixtures.

**⚠️ CRITICAL**: aucune story ne commence avant la fin de cette phase.

- [X] T006 Ajouter à `src/bitumap/config.py` les réglages `methode: str = "1.2"` (valeurs admises `1.2`, `2.0` ; toute autre valeur refusée au démarrage), `ete_reference: int | None = None` (défaut : dernier été disponible, fixé par l'acquisition, jamais la date du jour dans le calcul) et `station_meteo: str` (station de référence) ; les documenter dans `specs/002-on-demand-report/contracts/configuration.md` (`BITUMAP_METHODE`, `BITUMAP_ETE_REFERENCE`, `BITUMAP_STATION_METEO`, contrat 004 § 3)
- [X] T007 Rendre la version appliquée configurable dans `src/bitumap/score/methode.py` : `VERSION_METHODE` reste `"1.2"` ; ajouter `VERSION_METHODE_V2 = "2.0"` et `version_appliquee()` (lit `reglages().methode`) ; l'utiliser dans `src/bitumap/lot/commune.py` (journal) et `src/bitumap/lot/versions.py` (empreinte) à la place de `VERSION_METHODE`
- [X] T008 Ajouter au modèle `Facteur` de `src/bitumap/modele.py` un champ `details: dict[str, str | float | int | None]` (défaut vide) sérialisé dans `points.geojson` et la fiche (data-model : `cause_ombre`, `source`, `millesime_lidar`, `annee`, `troncon`) ; ajouter à `Point` `niveau_v1: str | None` et `raison_changement: str | None` (nuls en 1.2) ; vérifier que la sortie 1.2 est inchangée (`tests/rapport/test_rendu.py`)
- [X] T009 Étendre le protocole `Fournisseur` de `src/bitumap/sources/fournisseur.py` avec les accès v2, appelés **seulement** en méthode 2.0 : `hauteurs(lon, lat) -> (Provenance, mns, mnt, transform) | None` (carré de 200 m à 1 m autour du point, comme `vegetation`, R1 mesuré), `temperature_surface(emprise, ete) -> (Provenance, raster) | None`, `comptages_pl(emprise) -> (Provenance, GeoDataFrame)`, `meteo(station, ete) -> (Provenance, list[dict]) | None` ; implémenter l'enregistrement (`Enregistreur`) et la relecture (`FournisseurFige`) comme pour les sources existantes
- [X] T010 Intégrer l'**été de référence** à l'empreinte en méthode 2.0 dans `src/bitumap/lot/versions.py` (`empreinte_pour`) ; un nouvel été ⇒ nouvelle empreinte (FR-007) ; en 1.2, empreinte strictement inchangée ; millésime LiDAR et année des comptages inscrits dans le rapport, hors empreinte (R8, précisé au développement)
- [X] T011 Poser le mécanisme de fixtures des données 2.0 : `Enregistreur` fige hauteurs (`hauteurs.npz`), température de surface (`temperature.npz` + `temperature.json.gz`), comptages (`comptages.gpkg`) et météo (`meteo.json.gz`) ; `FournisseurFige` les relit et répond « absent » pour un dossier figé avant 004. **La capture sur Courbevoie se fait avec chaque adaptateur** (T016, T024, T026, T032), qui complète `tools/figer_fixtures.py` pour sa source ; taille totale des fixtures indiquée dans chaque PR (rééchantillonner si > 20 Mo)
- [X] T012 Écrire `tests/unit/test_methode_v2.py` : `BITUMAP_METHODE` absent ⇒ 1.2, empreinte et journal inchangés ; `2.0` ⇒ version 2.0 dans l'empreinte et le journal ; valeur inconnue ⇒ erreur au démarrage ; nouvel été de référence ⇒ nouvelle empreinte

**Checkpoint**: `BITUMAP_METHODE=2.0` produit un rapport (encore identique au 1.2 hors version) ; toutes les fixtures v2 sont lisibles hors réseau.

---

## Phase 3: User Story 1 - Un ensoleillement qui correspond à la rue réelle (Priority: P1) 🎯 MVP

**Goal**: heures de soleil juin–août calculées sur les hauteurs LiDAR HD, avec la cause principale d'ombre (FR-001 à FR-004).

**Independent Test**: sur Courbevoie figée en 2.0, A27418 reste à l'ombre du pont (cause « ouvrage »), un point sous des arbres hauts perd des heures par rapport à la 1.2, deux rues d'orientation différente diffèrent.

### Tests for User Story 1

- [X] T013 [P] [US1] Écrire `tests/adaptateurs/test_lidar.py` : lecture des dalles figées (MNS, MNT) ; assemblage de deux dalles voisines ; dalle absente ⇒ `None` sans exception ; provenance « IGN LiDAR HD », Licence Ouverte, millésime
- [X] T014 [P] [US1] Écrire `tests/unit/test_ensoleillement_v2.py` : grilles synthétiques (sans réseau) — rue canyon est-ouest contre nord-sud ⇒ heures différentes comme la course du soleil l'impose ; arbre mesuré de 15 m ⇒ moins d'heures qu'un arbre forfaitaire de 8 m ; relief (MNT incliné) pris en compte ; cause d'ombre `batiment`, `arbre`, `ouvrage`, `relief` selon l'obstacle qui bloque le plus de rayons ; 6 jours × 12 instants horaires (1er et 15 de juin, juillet, août, 8 h 30–19 h 30) ; carrefour : 5 points sur les voies bus à moins de 10 m du centre ; dalle absente ⇒ repli 1.2, `details.source = "repli_1.2"`, explication « ensoleillement estimé (données de hauteur incomplètes) »
- [X] T015 [P] [US1] Compléter `tests/unit/test_ouvrages.py` pour la 2.0 : chaussée sous un tablier mesuré par le MNS ⇒ cause « ouvrage » ; bus sur un pont ⇒ pas d'ombre du tablier ; zone d'arrêt au bord du tablier (cas de l'issue #18)

### Implementation for User Story 1

- [X] T016 [US1] Créer `src/bitumap/sources/lidar.py` : extraction par point (carré de 200 m à 1 m) du MNS et du MNT par `GetMap` GeoTIFF sur `https://data.geopf.fr/wms-r/wms` (couches `IGNF_LIDAR-HD_{MNS|MNT}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93`, R1), millésime lu dans l'index `IGNF_LIDAR-HD_METADONNEE:metadata` (`code_mission`, `date_edition`), cache par point dans le bucket de cache, provenance IGN LiDAR HD, Licence Ouverte ; méthode `hauteurs` de `FournisseurEnLigne` ; capture des hauteurs des points de Courbevoie dans `tools/figer_fixtures.py` (T011)
- [X] T017 [US1] Implémenter dans `src/bitumap/facteurs/ensoleillement.py` la variante 2.0 (sans toucher au chemin 1.2) : hauteur d'obstacle = MNS − altitude du sol au point (MNT) ; positions du soleil sur les 6 jours représentatifs de 8 h à 20 h (R2) ; heures = moyenne ; même effet borné `effet_heures` que la 1.2 ; zone de mesure de la 1.2 pour un arrêt, 5 points sur les voies bus à moins de 10 m pour un carrefour ou un giratoire ; repli 1.2 point par point si la dalle manque
- [X] T018 [US1] Implémenter la cause principale d'ombre dans `src/bitumap/facteurs/ensoleillement.py` (R2) : pour chaque rayon bloqué, obstacle classé `batiment` (emprise BD TOPO), `ouvrage` (sous un tablier OSM, fonction `tabliers` existante), `arbre` (hauteur > 2 m hors bâti, végétation de l'infrarouge déjà lue) ou `relief` ; cause = classe qui bloque le plus de rayons ; `details` : `cause_ombre`, `source` (`lidar_hd` ou `repli_1.2`), `millesime_lidar`
- [X] T019 [US1] Brancher la variante dans `src/bitumap/calcul.py` : en 2.0, lire `fournisseur.hauteurs(lon, lat)` pour chaque point et appeler l'ensoleillement 2.0 ; en 1.2, code inchangé
- [X] T020 [US1] Afficher dans la fiche (`src/bitumap/rapport/gabarits/rapport.html.j2`, `src/bitumap/rapport/rendu.py`) les heures juin–août, la cause principale d'ombre en clair (« bâtiment », « arbre », « ouvrage », « relief ») et la source (« LiDAR HD 2024 » ou « estimé ») ; test dans `tests/rapport/test_rendu.py`

**Checkpoint**: US1 testable seule avec `BITUMAP_METHODE=2.0` ; la 1.2 reste inchangée.

---

## Phase 4: User Story 2 - Une chaleur qui distingue vraiment les points (Priority: P1)

**Goal**: indicateurs de chaleur candidats calculés un par un, affichés avec l'été de référence ; seuls les indicateurs **retenus** (liste de la méthode, vide tant que la validation n'a pas eu lieu) entrent dans le score (FR-005 à FR-008).

**Independent Test**: sur Courbevoie figée en 2.0, une place minérale et une rue arborée de même trafic ont des indicateurs nettement différents ; le rapport indique l'été de référence ; un indicateur non retenu est affiché « non retenu (apport non démontré) » sans effet sur le score.

### Tests for User Story 2

- [ ] T021 [P] [US2] Écrire `tests/adaptateurs/test_temperature.py` : médiane des scènes figées de l'été de référence au point (fenêtre de 30 m) ; été sans scène exploitable ⇒ été précédent, indiqué ; provenance USGS marquée **hors UE**
- [ ] T022 [P] [US2] Écrire `tests/adaptateurs/test_meteo.py` : lecture des fixtures ; jours de forte chaleur de l'été (seuil de R4 documenté dans le test) ; source absente ⇒ `None` sans exception
- [ ] T023 [P] [US2] Écrire `tests/unit/test_chaleur_v2.py` : `temperature_surface` (°C), `mineralisation` (% de surfaces non végétales dans 50 m), `contexte_urbain` (zone climatique IPR) ; donnée absente ⇒ `statut = "non_evalue"`, effet 1,0 ; indicateur non retenu ⇒ affiché, effet 1,0 ; indicateur retenu ⇒ effet borné (bornes fixées d'avance) ; canicules : identiques pour tous les points de la commune, **jamais un facteur de classement** (R4)

### Implementation for User Story 2

- [ ] T024 [P] [US2] Créer `src/bitumap/sources/temperature.py` : recherche des scènes Landsat C2 L2 de juin–août de l'été de référence couvrant l'emprise, masque de nuages, médiane par pixel ; cache `lst/{ete}/{insee}.tif` ; repli sur l'été précédent ; provenance « USGS Landsat Collection 2 niveau 2 », domaine public, **hors UE** ; authentification M2M de l'USGS (`BITUMAP_USGS_UTILISATEUR`, `BITUMAP_USGS_JETON`, `login-token`, puis `download-options` / `download-request`), sans identifiants ⇒ « non évalué » ; méthode `temperature_surface` de `FournisseurEnLigne` ; capture de l'été de référence sur Courbevoie (T011) — **exige l'accès MACHINE accordé par l'USGS**
- [X] T025 [P] [US2] ~~Créer `src/bitumap/sources/dpe.py` : DPE logements existants et tertiaire de l'emprise, filtrés sur l'équipement de refroidissement, rattachés aux bâtiments BD TOPO ; cache `dpe/{departement}/{date}.parquet` ; provenance ADEME, Licence Ouverte~~ *(Sans objet : climatiseurs écartés de la 2.0, décision du mainteneur du 2026-09-30, research R4.)*
- [ ] T026 [P] [US2] Créer `src/bitumap/sources/meteo.py` (ou reprendre celui de 007, T005) : températures quotidiennes de l'été à la station `BITUMAP_STATION_METEO`, jours de forte chaleur ; cache `meteo/{station}/{ete}.json` ; provenance Météo-France, Licence Ouverte ; méthode `meteo` de `FournisseurEnLigne` ; capture de l'été de référence à la station (T011)
- [ ] T027 [US2] Implémenter les candidats dans `src/bitumap/facteurs/chaleur.py` (chemin 1.2 inchangé) : un `Facteur` par indicateur (`chaleur_temperature_surface`, `chaleur_mineralisation`, `chaleur_contexte_urbain`, et l'aléa actuel `chaleur_alea` comme référence) ; liste `INDICATEURS_CHALEUR_RETENUS` dans `src/bitumap/score/methode.py`, **vide** à ce stade (décision après validation, FR-006) : un indicateur non retenu est affiché avec effet 1,0 et l'explication « non retenu (apport non démontré) »
- [ ] T028 [US2] Brancher la chaleur 2.0 dans `src/bitumap/calcul.py` (lecture des sources une fois par commune) et ajouter au rapport `ete_reference` (année, jours de forte chaleur) ; synthèse et section « Sources » : été de référence, source hors UE déclarée (FR-014) dans `src/bitumap/rapport/rendu.py` et `rapport.html.j2`
- [ ] T029 [US2] Mesurer SC-003 sur Courbevoie figée dans `tests/non_regression/test_courbevoie_v2.py` : écart entre les 10 % les plus exposés et les 10 % les moins exposés pour chaque candidat, comparé à l'aléa 1.2 ; **consigner** les valeurs (pas encore bloquant : l'indicateur n'est retenu qu'après validation)

**Checkpoint**: US1 et US2 fonctionnent ensemble en 2.0 ; aucun indicateur de chaleur n'influence encore le score sans décision du mainteneur.

---

## Phase 5: User Story 3 - Le trafic poids lourds mesuré pris en compte (Priority: P2)

**Goal**: effet borné fondé sur les seuls comptages publiés ; « non évalué » sans comptage ; part des points couverts dans la synthèse (FR-009, FR-010).

**Independent Test**: sur Courbevoie figée en 2.0, un point sur une départementale comptée à fort trafic poids lourds reçoit un effet plus fort qu'un point de même charge bus sur une voie comptée faible ; une voie communale reçoit ×1,0 « non évalué (aucun comptage publié) ».

### Tests for User Story 3

- [X] T030 [P] [US3] Écrire `tests/adaptateurs/test_comptages.py` : comptages figés des Hauts-de-Seine et du réseau national ; normalisation (tronçon, poids lourds par jour, année, source) ; département sans comptage publié (inventaire T003) ⇒ liste vide
- [X] T031 [P] [US3] Écrire `tests/unit/test_poids_lourds.py` : rattachement à la **même voie** (même numéro de route ou même nom normalisé, à moins de 30 m) ; tronçon d'une autre voie à 10 m ⇒ non rattaché ; effet croissant borné de ×1,0 à ×1,25 ; sans comptage ⇒ ×1,0, `statut = "non_evalue"`, explication « non évalué (aucun comptage publié) », **quel que soit le type de route** ; `details` : `source`, `annee`, `troncon`

### Implementation for User Story 3

- [X] T032 [US3] Créer `src/bitumap/sources/comptages.py` : un lecteur par source retenue en T003 (Hauts-de-Seine, réseau national, autres départements publiés), sortie commune (géométrie Lambert 93, poids lourds par jour, année, source) ; cache `comptages/{source}/{annee}.json` ; méthode `comptages_pl` de `FournisseurEnLigne` ; capture sur Courbevoie (T011)
- [X] T033 [US3] Créer `src/bitumap/facteurs/poids_lourds.py` : rattachement (réutiliser `normaliser_numero` de `src/bitumap/facteurs/voirie.py` et `_normaliser_nom` de `src/bitumap/calcul.py`), effet borné (forme et bornes dans `src/bitumap/score/methode.py`, calibrées plus tard sur les relevés, R7)
- [X] T034 [US3] Brancher le facteur dans `src/bitumap/calcul.py` en 2.0 ; ajouter au rapport `couverture_poids_lourds` et l'afficher dans la synthèse ; fiche : valeur, source et année, ou « non évalué (aucun comptage publié) » (`rendu.py`, `rapport.html.j2`)

*Écarts au développement (2026-10-01, research R5 « Mesuré au développement, US3 »)* : pas de
cache (comme le LiDAR : une requête pour le 92, une archive d'environ 2 Mo pour le réseau
national) ; réseau national limité au **dernier millésime publié** (autoroutes concédées) ;
**bus du sens retirés** des poids lourds comptés ; effet linéaire en logarithme des PL/jour du
sens le plus chargé, de ×1,0 (50) à ×1,25 (2000) ; `normaliser_nom` déplacé de `calcul.py`
dans `facteurs/voirie.py` (import circulaire évité) ; sources déclarées dans le catalogue
`sources/comptages.toml` et lues par un lecteur générique par plateforme (revue de la PR #33).

**Checkpoint**: US1 à US3 fonctionnent en 2.0.

---

## Phase 6: User Story 4 - Comprendre ce qui change entre les versions (Priority: P2)

**Goal**: chaque point qui change de niveau porte son niveau 1.2 et la raison principale ; le mainteneur dispose d'un bilan et d'un outil de validation (FR-011 à FR-013, SC-004).

**Independent Test**: Courbevoie figée en 2.0 : 100 % des points qui changent de niveau ont `niveau_v1` et `raison_changement` ; tableau v1 × v2 dans la synthèse ; l'outil d'évaluation produit son rapport sur des relevés synthétiques.

### Tests for User Story 4

- [ ] T035 [P] [US4] Écrire `tests/unit/test_comparaison.py` : même point calculé en 1.2 et en 2.0 ; raison = facteur dont l'effet a le plus varié en logarithme (R6) ; niveau inchangé ⇒ raison nulle ; aucun appel d'IA supplémentaire (réponses en cache réutilisées) ; libellé « v1 : Sérieux — raison : chaleur, minéralisation forte »
- [ ] T036 [P] [US4] Écrire `tests/unit/test_evaluer_methode.py` : relevés synthétiques au format de l'export de 003 (`releves.geojson`) ; refus explicite sous 100 points ou 3 communes ; orniéré = « marqué » ou « grave » ; SC-001 (part des orniérés dans Critique + Sérieux + Important, v1 contre v2) ; apport d'un indicateur (avec et sans ; retenu si ≥ +2 points **et** aucune commune dégradée) ; SC-002 (écart moyen calculé / observé) ; sections du contrat 004 § 2 dans le Markdown produit

### Implementation for User Story 4

- [ ] T037 [US4] Créer `src/bitumap/score/comparaison.py` : dans le même lot, calcul 1.2 des points (réutilisation des sources et des réponses d'IA déjà en cache), `niveau_v1`, `raison_changement` ; bilan `bilan_changements` (nombre de points par couple niveau v1, niveau v2) ; branché dans `src/bitumap/lot/commune.py` en 2.0 seulement
- [ ] T038 [US4] Afficher dans le rapport (`rendu.py`, `rapport.html.j2`) : dans la fiche, « v1 : <niveau> — raison : <facteur> » si le niveau change ; dans la synthèse, le tableau niveau v1 × niveau v2 ; dans la section Méthode, version 2.0, facteurs et bornes, indicateurs non retenus et pourquoi, sources dont celle hors UE
- [ ] T039 [US4] Créer `src/bitumap/methode/__init__.py` et `src/bitumap/methode/evaluer.py` (sur le modèle de `src/bitumap/ia/evaluer.py`) : `python -m bitumap.methode.evaluer --releves <geojson|csv> --communes … [--sortie evaluation-v2.md]` ; calcul des communes de référence en 1.2 et en 2.0 (avec et sans chaque indicateur candidat) ; Markdown aux sections du contrat 004 § 2 ; recommandation marquée « à confirmer par le mainteneur »
- [ ] T040 [US4] Adapter la non-régression dans `tests/non_regression/test_courbevoie_v2.py` (R8) : Courbevoie figée en 2.0 ; deux générations identiques au point près (SC-006) ; 100 % des changements de niveau expliqués (SC-004) ; A27418 « Verdun - Rue Latérale » cause « ouvrage », non Critique (issue #18) ; durée < 2 × celle de la 1.2 sur la même machine (SC-005, mesurée et consignée) ; `tests/non_regression/test_courbevoie.py` (1.2) inchangé et toujours vert

### Réfection confirmée : classement corrigé par le terrain (R9, FR-016 à FR-018)

Ajouté après la clarification du 2026-09-30 (cas A36862 « Hérold - Mairie de Courbevoie »).
**Couche distincte, calculée au service du rapport** : le score estimé, `points.geojson` et
l'empreinte ne sont jamais modifiés par un relevé (constitution, principe VI).

**Independent Test**: rapport 2.0 de Courbevoie servi avec un relevé « réfection 2020,
constatée, niveau absent » sur A36862 et l'été de référence 2026 : classement estimé
inchangé (rang 1) ; classement corrigé par le terrain avec l'effet ×0,8 et un rang plus bas.

- [ ] T046 [P] [US4] Écrire `tests/unit/test_classement_terrain.py` (fonctions pures, sans base) : effet `min(1,0 ; 0,5 + 0,05 × n)` avec `n = ete_reference − annee_refection` borné à ≥ 0 (×0,5 l'année des travaux, ×0,8 à 6 ans, ×1,0 à 10 ans et au-delà) ; seules les sources `constatee` et `services_techniques` comptent, `estimee_agent` sans effet (FR-016) ; plus récente année confirmée parmi les relevés visibles du point ; annulation si le relevé visible **le plus récent** du point est daté d'une année ≥ `annee_refection` et constate `marque` ou `grave`, motif « réfection sans effet : orniérage constaté après les travaux » (FR-018) ; rangs et niveaux corrigés obtenus par les mêmes règles que l'estimé (`score.combinaison`, priorités figées avant l'âge de l'enrobé) ; point sans réfection confirmée absent du bloc ; aucune donnée personnelle dans le résultat (ni auteur, ni adresse, ni photo) ; même entrée ⇒ même sortie
- [ ] T047 [P] [US4] Écrire `tests/api/test_rapport_classement_terrain.py` : rapport 2.0 servi ⇒ bloc `<script type="application/json" id="classement-terrain">` inséré **après** le bloc `releves` et **avant** le script (LL-012) ; rapport 1.2 ⇒ aucun bloc ; relevé retiré ⇒ plus d'effet ; `rapport.html` et `points.geojson` stockés inchangés ; CSP du document servi inchangée (bloc JSON exclu, LL-011) ; même rapport consulté deux fois ⇒ même bloc
- [ ] T048 [US4] Créer `src/bitumap/terrain/classement.py` : `refections(commune_insee)` lit **tous** les relevés visibles de la commune (dernière version, via la requête de `src/bitumap/terrain/depot.py`, filtre constant et valeurs en paramètres) et retient par point l'année confirmée et le dernier relevé ; `corriger(points_geojson, refections, ete_reference)` reconstruit les `Point` (facteurs et effets du `points.geojson` du rapport), applique l'effet au score brut, reclasse avec `src/bitumap/score/combinaison.py` et renvoie `{"points": {id: {annee_refection, source_refection, effet, annule, motif, rang, groupe}}, "nb_points_corriges": n}` (data-model, R9)
- [ ] T049 [US4] Lire, pour un rapport servi, sa version de méthode et son été de référence (`journal.json` et champ `ete_reference` du rapport, T028) dans `src/bitumap/api/demandes.py` ; rapports 1.x ou sans été de référence : pas de classement corrigé
- [ ] T050 [US4] Insérer le bloc `classement-terrain` dans `rapport()` de `src/bitumap/api/demandes.py`, juste après le bloc `releves` (fonction `_inserer_avant_script` existante) ; rien n'est écrit dans le stockage
- [ ] T051 [US4] Afficher la couche dans le rapport 2.0 (`src/bitumap/rapport/interactions.js`, `src/bitumap/rapport/gabarits/rapport.html.j2`) : fiche « Estimé : rang R, niveau · Corrigé par le terrain : rang R', niveau' (réfection de AAAA, constatée : ×E) » ou le motif d'annulation ; liste : choix « classement estimé / corrigé par le terrain » (**estimé par défaut**) ; synthèse « N points corrigés par une réfection confirmée » ; bloc absent ⇒ rien d'affiché (rapports en cache, LL-011) ; test de rendu dans `tests/rapport/test_rendu.py`
- [ ] T052 [US4] Documenter le bloc dans `specs/003-terrain-releves/contracts/http-api.md` (rapport servi) et `specs/002-on-demand-report/contracts/report-bundle.md` (affichage) ; dérouler le quickstart 004 § 5 dans un navigateur (LL-012) et consigner le résultat dans la PR

**Checkpoint**: la 2.0 est complète derrière `BITUMAP_METHODE` ; la mise en service attend la validation (FR-013).

---

## Phase 7: Polish & sujets transverses

- [ ] T041 [P] Rédiger l'entrée **2.0** de `docs/methode/CHANGELOG.md` (FR-011) : facteurs, bornes, sources, repli, limites connues, source hors UE ; section « Indicateurs de chaleur » : climatiseurs **écartés** dès la 2.0 (couverture des DPE, research R4, décision du mainteneur du 2026-09-30, à réexaminer plus tard), les autres à compléter après validation (retenus et écartés, avec la raison)
- [ ] T042 [P] Mettre à jour `specs/002-on-demand-report/contracts/report-bundle.md` (champs de data-model 004 : `details`, `niveau_v1`, `raison_changement`, `ete_reference`, `couverture_poids_lourds`, `bilan_changements`) et le `README.md` (section « Méthode de score » : la 2.0 en préparation derrière un réglage ; sources ajoutées ; feuille de route 004 en cours)
- [ ] T043 [P] Préparer pour le mainteneur le texte de l'**amendement MINEUR du principe III** (liste des sources : IGN LiDAR HD, USGS hors UE déclaré, Météo-France, comptages départementaux et nationaux) dans `specs/004-methode-v2/amendement-principe-III.md` ; la modification de `.specify/memory/constitution.md` reste une PR humaine (CODEOWNERS)
- [ ] T044 Revue de sécurité de la branche (`/security-review`) : appels réseau du job (HTTPS, délais, taille bornée des téléchargements, aucune URL construite depuis une saisie), aucun secret ajouté, données mises en cache dans le bucket privé ; corriger les constats
- [ ] T045 Exécuter le quickstart § 2 et § 3 sur fixtures ; `uv run pytest` complet ; `ruff check` et `ruff format --check` ; consigner la durée v2 / 1.2 (SC-005) dans la description de la PR

---

## Dependencies & Execution Order

- **Setup (T001–T005)** : avant tout code de source ; T001 bloque US1, T002/T004/T005 bloquent US2, T003 bloque US3.
- **Foundational (T006–T012)** → stories. La capture des fixtures de chaque source se fait avec son adaptateur (T011).
- **US1 (T013–T020)** : MVP ; dépend de la phase 2.
- **US2 (T021–T029)** : dépend de la phase 2 ; indépendante de US1 (fichiers distincts), sauf `calcul.py` (T019 puis T028).
- **US3 (T030–T034)** : dépend de la phase 2 ; `calcul.py` après T028.
- **US4 (T035–T040)** : après US1 à US3 (compare la 2.0 complète à la 1.2).
- **Réfection confirmée (T046–T052)** : dépend de T028 (`ete_reference` dans le rapport) ; indépendante de T035–T040 (fichiers distincts), sauf `rapport.html.j2` et `interactions.js` (T038 puis T051).
- **Polish (T041–T045)** : après les stories ; T043 peut être fait à tout moment.
- **Mise en service (hors de ces tâches)** : 003 en service, au moins 100 relevés dans 3 communes, outil d'évaluation (T039), indicateurs retenus inscrits dans `INDICATEURS_CHALEUR_RETENUS`, amendement du principe III fusionné, puis `BITUMAP_METHODE=2.0` par le mainteneur.

### Parallel Opportunities

```text
T002 T003 T004 T005                  (Setup, sources distinctes)
T013 T014 T015                       (tests US1)
T021 T022 T023                       (tests US2)
T024 T026                            (sources US2)
T030 T031                            (tests US3)
T035 T036 T046 T047                  (tests US4, réfection comprise)
T041 T042 T043                       (Polish)
```

## Implementation Strategy

1. **Setup + Foundational** : lever les inconnues des sources, puis la sélection de méthode
   et les fixtures ; rien ne change pour la 1.2.
2. **MVP = US1** (ensoleillement LiDAR) : le gain le plus sûr, indépendant de la validation
   (issue #18, arbres mesurés, relief).
3. **US2 et US3** : indicateurs calculés et affichés, sans effet sur le score tant que la
   validation n'a pas eu lieu (chaleur) ; poids lourds borné sur mesure.
4. **US4** : explication des changements et outil de validation, prêts pour la campagne de
   relevés ; classement corrigé par le terrain (réfection confirmée, T046–T052), utile dès
   les premiers relevés.
5. Une PR par étape livrable (Setup + Foundational + US1, puis US2 + US3, puis US4 +
   Polish), relue et fusionnée par le mainteneur (principe IX).
