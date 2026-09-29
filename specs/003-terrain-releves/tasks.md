---
description: "Tâches d'implémentation des relevés terrain"
---

# Tasks: Relevés terrain

**Input**: Documents de conception dans `/specs/003-terrain-releves/`

**Prerequisites**: plan.md, spec.md (clarifications du 2026-09-29), research.md (R1–R12),
data-model.md, contracts/http-api.md, quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des tests sans réseau ; la spec
définit des critères vérifiables (SC-003, SC-004, SC-005, SC-006, SC-009). Écrire les tests
de chaque story **avant** son implémentation et vérifier qu'ils échouent.

**Organization**: tâches groupées par user story (US1 à US5 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US5

## Règles communes

- Aucune nouvelle dépendance Python (plan) ; aucune bibliothèque JavaScript (script écrit à
  la main, sans outil de construction).
- Aucune donnée personnelle dans les journaux (adresse, position) ; aucun secret dans le code.
- Messages d'erreur sans détail technique (002 FR-025) ; codes d'erreur du contrat.
- Toute route `/terrain/…` exige une session ; toute écriture exige le jeton `csrf`.
- Commits sur la branche `003-terrain-releves`, fichiers nommés explicitement (LL-002) ;
  fermer dans l'éditeur les fichiers d'autres branches (LL-010).

---

## Phase 1: Setup (infrastructure partagée)

- [ ] T001 Ajouter à `src/bitumap/config.py` : `bucket_terrain` (`BITUMAP_BUCKET_TERRAIN`, défaut `bitumap-terrain`), `photos_max_go` (`BITUMAP_PHOTOS_MAX_GO`, défaut 20), `quota_releves_compte_jour` (200), `quota_photos_compte_jour` (1 000), `photos_par_releve` (5), `photo_max_octets` (10 Mo), `photo_formulaire_validite_s` (300) ; documenter ces réglages dans `specs/002-on-demand-report/contracts/configuration.md`
- [ ] T002 Créer `src/bitumap/db/migrations/003_releves.sql` : tables `releve`, `releve_version`, `photo` exactement selon `data-model.md` — dont `releve.compte_id` « uuid, nul, → compte, ON DELETE SET NULL », `releve_version.niveau` « énuméré obligatoire : absent, leger, marque, grave », `profondeur_mm` « 0 à 200 », `observation` « 1 000 caractères au plus », `annee_refection` « 1950 à l'année en cours » (contrôle applicatif pour la borne haute), `source_refection` « constatee, services_techniques, estimee_agent ; requis si année », `instrument` « requis si profondeur_mm », `incoherence_confirmee` booléen, `photo.etat` « quarantaine → visible ; retiree_auteur, retiree_mainteneur », clé `(releve_id, version)`, index `(commune_insee, point_id, cree_le DESC)`
- [ ] T003 [P] Créer le bucket `bitumap-terrain` (versionné) dans le stockage simulé local (`compose.yaml` ou script de préparation de moto) et dans la fixture `s3` de `tests/conftest.py`
- [ ] T004 [P] Créer `tests/fixtures/terrain/` : une photo JPEG avec métadonnées EXIF (GPS, modèle d'appareil, auteur, date), une photo PNG, un fichier texte renommé `.jpg`, une image de 12 Mo ; documenter leur origine (générées par un script de test, aucune photo réelle)
- [ ] T005 [P] Ajouter à `tests/conftest.py` une aide `connecter_mainteneur(client, courriels)` (compte dont l'adresse est `BITUMAP_EMAIL_MAINTENEUR`) et une aide `rapport_courbevoie(s3)` qui produit le rapport figé de Courbevoie

**Checkpoint**: migration appliquée, bucket et fixtures prêts

---

## Phase 2: Foundational (prérequis bloquants)

- [ ] T006 Écrire `tests/api/test_rapport_csp.py` : un rapport stocké avec une **ancienne** version du script en ligne reste interactif — la CSP servie autorise l'empreinte du script du document servi (R2) ; un document sans script en ligne est servi avec `script-src 'none'`
- [ ] T007 Corriger `src/bitumap/api/demandes.py` (route `GET /rapports/{insee}/{empreinte}`) : calculer l'empreinte `sha256` du script en ligne **du document servi** au lieu de `CSP_RAPPORT` fixe (R2) ; ajouter l'entrée `LESSON-LEARNED.md` (défaut latent de 002 : rapports en cache cassés après modification du script) avec ce test comme mesure préventive
- [ ] T008 [P] Implémenter `src/bitumap/terrain/pseudonyme.py` : `pseudonyme(compte_id, email) -> "agent XXXX · domaine"`, `XXXX` = 4 caractères hexadécimaux d'un HMAC de l'identifiant du compte avec une clé dérivée de `sel_origine` (étiquette fixe, stable dans le temps) ; `domaine` = partie après `@` ; « auteur supprimé » si le compte n'existe plus ; test dans `tests/terrain/test_pseudonyme.py` (stable, distinct entre deux comptes, jamais l'adresse)
- [ ] T009 [P] Implémenter `src/bitumap/terrain/points.py` : lecture des points du rapport en vigueur d'une commune (`points.geojson` via `stockage`) : identifiant, désignation, groupe, position ; test sur le rapport figé de Courbevoie
- [ ] T010 Implémenter dans `src/bitumap/api/auth.py` `est_mainteneur(session) -> bool` (adresse du compte égale à `BITUMAP_EMAIL_MAINTENEUR`, comparaison insensible à la casse ; faux si non configuré) et la dépendance `MainteneurRequis` (`404` sinon)
- [ ] T011 Créer `src/bitumap/api/terrain.py` (routeur `/terrain`, session obligatoire) et l'enregistrer dans `src/bitumap/api/application.py` ; en-têtes propres aux pages de terrain : `Permissions-Policy: geolocation=(self)`, `connect-src 'self' https://{bucket_terrain}.s3.fr-par.scw.cloud`, `img-src 'self' blob: data:` (R9, contrat) ; toutes les autres routes gardent les en-têtes de 002

**Checkpoint**: CSP corrigée, briques communes testées

---

## Phase 3: User Story 1 - Consigner un relevé sur un point, depuis le terrain (Priority: P1) 🎯 MVP

**Goal**: saisie d'un relevé (niveau obligatoire, champs facultatifs, jusqu'à 5 photos) depuis un téléphone, même hors réseau

**Independent Test**: sur Courbevoie, relevé complet sur « Paix - Verdun » (A23742) avec deux photos, retrouvé en base ; saisie hors réseau envoyée au retour du réseau sans doublon

### Tests (écrire d'abord, ils doivent échouer)

- [ ] T012 [P] [US1] Écrire `tests/terrain/test_depot.py` : `PUT` crée un relevé (version 1) ; même `id` renvoyé ⇒ `200` sans doublon (idempotence, R3) ; `id` d'un autre compte ⇒ `409 identifiant_pris` ; sans niveau ⇒ `400 niveau_requis` ; point hors rapport ⇒ `404 point_inconnu` ; bornes de `data-model.md` (profondeur 0–200, observation ≤ 1 000 caractères, année 1950–année en cours, instrument requis si profondeur, source requise si année) ⇒ `400 saisie_invalide` ; 201ᵉ relevé du jour ⇒ `429 quota_releves` ; copie de `point_nom`, `point_designation`, `niveau_estime` à la saisie (R7) ; position à plus de 100 m ⇒ `distance_point_m` renseignée
- [ ] T013 [P] [US1] Écrire `tests/terrain/test_coherence.py` : repères FR-005b (léger < 10 mm, marqué 10–20 mm, grave > 20 mm) ; « léger » + 25 mm sans confirmation ⇒ `200` sans enregistrement, `{"avertissement": "mesure_incoherente", "niveau_suggere": "grave"}` ; avec `confirme_malgre_incoherence` ⇒ enregistré, `incoherence_confirmee = vrai` ; sans profondeur ⇒ aucun contrôle (R11)
- [ ] T014 [P] [US1] Écrire `tests/terrain/test_photos.py` : formulaire présigné (5 min, taille ≤ 10 Mo et type imposés par la politique) ; confirmation ⇒ photo `visible`, **aucune métadonnée EXIF** dans l'objet final, position conservée en base (SC-006) ; contenu non image ⇒ `400 image_invalide` et objet de quarantaine supprimé ; 6ᵉ photo ⇒ `409 trop_de_photos` ; photo d'un relevé d'un autre compte ⇒ `403 pas_auteur` ; 1 001ᵉ photo du jour ⇒ `429 quota_photos` ; plafond global atteint ⇒ `507 stockage_plein` et une alerte au mainteneur par jour ; confirmation rejouée ⇒ idempotente

### Implémentation

- [ ] T015 [US1] Implémenter `src/bitumap/terrain/depot.py` : création idempotente d'un relevé (identifiant fourni par le téléphone), version 1, contrôle des bornes de `data-model.md`, contrôle de cohérence niveau/profondeur (R11, même règle que le téléphone), distance au point, quotas `releve:compte:{id}:{jour}` via `bitumap.api.quotas`
- [ ] T016 [US1] Implémenter `src/bitumap/terrain/photos.py` : formulaire d'envoi présigné (POST, `content-length-range` ≤ `photo_max_octets`, type `image/jpeg` ou `image/png`, préfixe `quarantaine/`, validité `photo_formulaire_validite_s`) ; confirmation : relecture, décodage avec Pillow (FR-019), réencodage JPEG **sans aucune métadonnée**, écriture sous `communes/{insee}/points/{point_id}/{releve_id}/{photo_id}.jpg`, suppression de la quarantaine ; plafond global `photos_max_go` (somme de `photo.octets`) et alerte `stockage_photos:{jour}` via `bitumap.ia.budget.alerter_une_fois`
- [ ] T017 [US1] Ajouter à `src/bitumap/api/terrain.py` les routes `PUT /terrain/releves/{id}`, `POST /terrain/releves/{id}/photos/{photo_id}/formulaire`, `POST /terrain/releves/{id}/photos/{photo_id}/confirmation` (contrat : entrées, réponses, codes d'erreur)
- [ ] T018 [P] [US1] Créer les pages `src/bitumap/api/gabarits/terrain/points.html` (`GET /terrain/{insee}` : liste des points, recherche, filtre, dernier constat, compteur « en attente d'envoi ») et `src/bitumap/api/gabarits/terrain/saisie.html` (`GET /terrain/{insee}/{point_id}` : niveaux avec leurs repères, profondeur et instrument, observation, année et source de réfection, photos, historique du point) ; accessibles au clavier et au lecteur d'écran
- [ ] T019 [US1] Écrire `src/bitumap/api/statique/terrain/terrain.js` (sans dépendance) : identifiant UUID par relevé et par photo ; file d'attente dans IndexedDB (relevés et photos) ; envoi au chargement et à l'événement `online`, réenvoi idempotent ; redimensionnement des photos à 2 048 px en JPEG par `canvas` (R4) après lecture de la position de prise de vue ; champ fichier `accept="image/jpeg,image/png"` (conversion HEIC par Safari) ; position du téléphone facultative à la validation ; contrôle de cohérence immédiat avec « corriger / confirmer » (R11) ; `navigator.storage.persist()` ; alerte si un relevé attend depuis plus de 3 jours (R3) ; compteur « en attente d'envoi » toujours visible
- [ ] T020 [P] [US1] Créer `src/bitumap/api/statique/terrain/manifeste.webmanifest` et la route `GET /terrain/manifeste.webmanifest` (ajout à l'écran d'accueil, R3)
- [ ] T021 [US1] Valider à la main sur un téléphone (Safari iOS et Chrome Android) le parcours du quickstart § 2 (saisie) et § 3 (hors réseau) ; consigner le résultat dans la PR

**Checkpoint**: saisie fonctionnelle, y compris hors réseau (SC-001, SC-003)

---

## Phase 4: User Story 2 - Voir le constaté à côté de l'estimé dans le rapport (Priority: P1)

**Goal**: section « Constaté » dans la fiche, marqueurs, filtres, synthèse estimé × constaté, sans régénérer le rapport ni toucher au score

**Independent Test**: après un relevé, le rapport de Courbevoie ouvert par un autre compte montre le constaté ; score, rang et niveau inchangés ; photos invisibles pour lui

### Tests (écrire d'abord)

- [ ] T022 [P] [US2] Écrire `tests/api/test_rapport_releves.py` : le rapport servi contient un bloc `<script type="application/json" id="releves">` avec le dernier relevé visible de chaque point relevé (niveau, profondeur, instrument, année de réfection, observation, date, pseudonyme ou « vous », nombre de photos, « position éloignée ») et le nombre de relevés ; **aucun lien ni identifiant de photo** dans le bloc ; le rapport stocké dans le bucket est inchangé ; **score, rang et niveau de chaque point identiques** avant et après relevés (SC-004) ; un relevé retiré n'apparaît pas
- [ ] T023 [P] [US2] Écrire `tests/terrain/test_acces_photos.py` : `GET /terrain/photos/{id}` : auteur ⇒ image sans métadonnée, `Cache-Control: private, no-store` ; mainteneur ⇒ image ; autre compte ⇒ `404` (sans fuite d'existence) ; sans session ⇒ `401` ; vérification sur **tous** les points d'accès (fiche, historique, export) que seul le nombre de photos est exposé aux autres (SC-009)

### Implémentation

- [ ] T024 [US2] Implémenter dans `src/bitumap/terrain/depot.py` `derniers_releves(commune_insee, compte_id)` (dernier relevé visible par point, nombre de relevés, pseudonyme ou « vous ») et `historique(commune_insee, point_id)` (toutes les versions, du plus récent au plus ancien)
- [ ] T025 [US2] Modifier `src/bitumap/api/demandes.py` (`GET /rapports/{insee}/{empreinte}`) : insérer le bloc `releves` avant `</body>` à chaque consultation (JSON échappé comme `_json_dans_html` de `rapport/rendu.py`), sans modifier l'objet stocké
- [ ] T026 [US2] Ajouter `GET /terrain/photos/{photo_id}` et `GET /terrain/releves/{id}` dans `src/bitumap/api/terrain.py` (auteur ou mainteneur seulement pour les photos, `404` sinon)
- [ ] T027 [US2] Compléter `src/bitumap/rapport/interactions.js` et `src/bitumap/rapport/gabarits/rapport.html.j2` : section « Constaté » dans la fiche, distincte de « Estimé » (dernier relevé, auteur, date, « n photos, visibles par leur auteur », lien vers l'historique `/terrain/{insee}/{point_id}`) ; marqueur « relevé » sur la carte et dans la liste ; filtre « relevés / non relevés / par niveau constaté » ; synthèse estimé × constaté (FR-009) ; un rapport sans bloc `releves` (ancien) fonctionne comme avant
- [ ] T028 [US2] Afficher dans l'historique de commune (`GET /terrain/{insee}`) les points relevés **absents du rapport en vigueur** (R7, cas limite)

**Checkpoint**: constaté visible dans le rapport, score inchangé, photos protégées (SC-002, SC-004, SC-009)

---

## Phase 5: User Story 3 - Corriger ou retirer son relevé (Priority: P2)

**Goal**: nouvelle version à chaque correction, retrait par l'auteur avec trace

**Independent Test**: corriger le niveau puis retirer une photo : version corrigée affichée, deux versions dans l'historique, trace du retrait

- [ ] T029 [P] [US3] Écrire `tests/terrain/test_versions.py` : `POST /terrain/releves/{id}/versions` ⇒ version 2 affichée, version 1 dans l'historique, rien n'est modifié en place (SC-005) ; autre compte ⇒ `403 pas_auteur` ; retrait d'un relevé ou d'une photo par l'auteur ⇒ masqué partout, trace (qui, quand), fichier de photo **conservé** (R12) ; contrôle de cohérence (R11) aussi appliqué aux versions
- [ ] T030 [US3] Implémenter dans `src/bitumap/terrain/depot.py` et `src/bitumap/terrain/photos.py` : nouvelle version, retrait par l'auteur (`retire_le`, `retire_par`, `motif_retrait` ; `photo.etat = retiree_auteur`)
- [ ] T031 [US3] Ajouter `POST /terrain/releves/{id}/versions`, `POST /terrain/releves/{id}/retrait` et `POST /terrain/photos/{photo_id}/retrait` (auteur) dans `src/bitumap/api/terrain.py` ; boutons « Corriger » et « Retirer » sur `saisie.html` pour les relevés de l'utilisateur (hors réseau : la correction entre dans la même file d'attente que la saisie)

**Checkpoint**: historique fiable (SC-005)

---

## Phase 6: User Story 4 - Exporter les relevés d'une commune (Priority: P2)

**Goal**: export tableur, cartographique et échantillon de réfection pour T073 (002)

**Independent Test**: exporter Courbevoie et ouvrir dans un tableur et un logiciel de cartographie ; l'échantillon est lu par `bitumap.ia.evaluer`

- [ ] T032 [P] [US4] Écrire `tests/terrain/test_export.py` : CSV UTF-8 avec BOM, séparateur `;`, une ligne par relevé visible (dernière version), colonnes du contrat ; niveau estimé = rapport **en vigueur** ; liens de photos seulement pour les relevés de l'utilisateur ; GeoJSON WGS 84 aux mêmes champs ; `echantillon_refection.json` au format `{"points": [{id, nom, lon, lat, refection_annee, source}]}` limité aux sources `constatee` et `services_techniques`, accepté par `bitumap.ia.evaluer` (lecture seule, sans appel au modèle)
- [ ] T033 [US4] Implémenter `src/bitumap/terrain/export.py` (CSV, GeoJSON, échantillon de réfection)
- [ ] T034 [US4] Ajouter `GET /terrain/{insee}/releves.csv`, `GET /terrain/{insee}/releves.geojson`, `GET /terrain/{insee}/echantillon_refection.json` dans `src/bitumap/api/terrain.py`, et les liens d'export sur `points.html`

**Checkpoint**: export exploitable (SC-007)

---

## Phase 7: User Story 5 - Traiter une demande de retrait (Priority: P3)

**Goal**: retrait RGPD par le mainteneur ; anonymisation à la suppression d'un compte

**Independent Test**: retirer une photo en mainteneur : plus visible nulle part, plus aucune version dans le bucket ; compte supprimé ⇒ relevés « auteur supprimé »

- [ ] T035 [P] [US5] Écrire `tests/terrain/test_moderation.py` : `GET /terrain/moderation` réservé au mainteneur (`404` sinon) ; recherche par identifiant, commune ou point ; retrait RGPD d'une photo ⇒ `retiree_mainteneur`, **toutes les versions** de l'objet supprimées du bucket versionné, trace conservée sans fichier, absente du rapport et de l'export (SC-008) ; suppression d'un compte (002 `POST /compte/suppression`) ⇒ relevés visibles « auteur supprimé », photos visibles du seul mainteneur (FR-017)
- [ ] T036 [US5] Implémenter le retrait RGPD dans `src/bitumap/terrain/photos.py` (suppression de toutes les versions de l'objet : liste des versions puis suppression une à une) et la page `src/bitumap/api/gabarits/terrain/moderation.html` avec sa route `GET /terrain/moderation` dans `src/bitumap/api/terrain.py`
- [ ] T037 [US5] Vérifier dans `src/bitumap/api/compte.py` que la suppression de compte laisse les relevés (`ON DELETE SET NULL`) et que le pseudonyme devient « auteur supprimé » ; accès aux photos d'un auteur supprimé réservé au mainteneur

**Checkpoint**: obligations RGPD couvertes

---

## Phase 8: Polish & sujets transverses

- [ ] T038 [P] Compléter `src/bitumap/api/gabarits/confidentialite.html` : relevés (contenu, affichage de l'auteur en pseudonyme, adresse visible du mainteneur), photos (visibles de l'auteur et du mainteneur, **conservées sans limite de durée**, finalité : suivi de la voirie dans le temps), position de saisie facultative, retrait sur demande et contact (R12)
- [ ] T039 [P] Mettre à jour `specs/002-on-demand-report/contracts/http-api.md` (bloc `releves` du rapport, CSP calculée sur le document servi) et `specs/002-on-demand-report/contracts/report-bundle.md` (lien vers les relevés)
- [ ] T040 [P] Ajouter à la phase 7 de `specs/002-on-demand-report/tasks.md` une tâche d'infrastructure OpenTofu : bucket `bitumap-terrain` versionné, expiration du préfixe `quarantaine/` à 1 jour, règle CORS limitée à l'origine du service pour l'envoi présigné, droits de `bitumap-api` (lecture, écriture, suppression de versions)
- [ ] T041 [P] Mettre à jour le `README.md` (feuille de route : 003 en cours ; section Stockage : `bitumap-terrain` et tables de relevés au lieu des fichiers JSON initialement prévus)
- [ ] T042 Revue de sécurité de la branche (`/security-review`) : contrôle d'accès des photos, CSRF, formulaire présigné, en-têtes des pages de terrain ; corriger les constats
- [ ] T043 Exécuter le quickstart de bout en bout (§ 2 à § 6) et `uv run pytest` complet ; `ruff check` et `ruff format --check`

---

## Dependencies & Execution Order

- **Setup (T001–T005)** → **Foundational (T006–T011)** → stories.
- **US1 (T012–T021)** : MVP ; dépend de la phase 2.
- **US2 (T022–T028)** : dépend de T015 (relevés en base) ; indépendante du script de saisie (tests avec relevés créés par l'API).
- **US3 (T029–T031)** : dépend de T015–T017.
- **US4 (T032–T034)** : dépend de T024 (derniers relevés).
- **US5 (T035–T037)** : dépend de T016 (photos) et T026 (accès).
- **Polish** : après les stories ; T040 peut être fait à tout moment.
- **Mise en service** : après l'infrastructure de 002 (phase 7, dont T040).

### Parallel Opportunities

```text
T003 T004 T005                       (Setup, fichiers distincts)
T008 T009                            (Foundational)
T012 T013 T014                       (tests US1)
T018 T020                            (pages et manifeste US1)
T022 T023                            (tests US2)
T029 T032 T035                       (tests US3, US4, US5, une fois US1 faite)
T038 T039 T040 T041                  (Polish)
```

## Implementation Strategy

1. **MVP = US1 + US2** (P1) : saisir et voir le constaté ; c'est ce qui débloque la validation
   de 004 et l'échantillon de T073.
2. **US3 et US4** (P2) : fiabilité (corrections) et usage par les services (export).
3. **US5** (P3) : obligatoire avant toute mise en service publique (RGPD).
4. Une PR par étape livrable (MVP, puis P2, puis P3), relue et fusionnée par le mainteneur
   (principe IX).
