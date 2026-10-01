---
description: "Tâches d'implémentation du parcours de surveillance"
---

# Tasks: Parcours de surveillance

**Input**: Documents de conception dans `/specs/006-parcours-surveillance/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R8), data-model.md,
contracts/http-api.md, quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des tests sans réseau : géocodage et
itinéraire simulés (respx), GPX validé contre le schéma 1.1 (quickstart § 2). Écrire les tests
de chaque story **avant** son implémentation et vérifier qu'ils échouent.

**Organization**: tâches groupées par user story (US1 à US4 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US4

## Règles communes

- **Aucun effet sur le score** (principe IV) : l'ordre de visite est le **rang estimé** du
  rapport en vigueur (`terrain.points.points_en_vigueur`), jamais le classement corrigé par le
  terrain de 004 (couche d'affichage).
- **Aucune nouvelle dépendance** (plan) : GPX avec `xml.etree.ElementTree` de la bibliothèque
  standard ; HTTP avec `httpx` et `sources.base.client_http`.
- **Appels externes** (LL-019) : URL de base constantes du code ; toute adresse lue dans une
  réponse tierce passe par `sources.base.verifier_url` ; tout fichier téléchargé par
  `sources.base.telecharger` (taille bornée). Aucun appel réseau dans les tests.
- **Données personnelles** (FR-012, SC-006) : l'adresse de départ n'est jamais écrite dans
  les journaux (ni dans `evenement`, ni dans un message d'exception) ; conservée 24 h au plus.
- Commits sur la branche `006-parcours-surveillance`, fichiers nommés explicitement (LL-002) ;
  une PR par étape livrable ; jamais de fusion par l'agent (principe IX).

---

## Phase 1: Setup

**Purpose**: table éphémère, structure du module et des tests.

- [ ] T001 Créer la migration `src/bitumap/db/migrations/005_parcours.sql` (numéro 005 : la dernière existante est `004_photo_retrait.sql` ; le plan disait 006) : table `parcours` du data-model — `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`, `compte_id uuid NOT NULL REFERENCES compte(id) ON DELETE CASCADE`, `commune_insee text NOT NULL`, `empreinte text NOT NULL`, `depart_libelle text NOT NULL`, `depart_lon double precision NOT NULL`, `depart_lat double precision NOT NULL`, `niveaux text[] NOT NULL` (« parmi `P1a` … `P3` ; au moins un » : `CHECK (cardinality(niveaux) >= 1 AND niveaux <@ ARRAY['P1a','P1b','P1c','P2','P3'])`), `mode text NOT NULL CHECK (mode IN ('voiture','pied'))`, `duree_max_min integer NOT NULL CHECK (duree_max_min BETWEEN 30 AND 480)` (180 par défaut côté formulaire), `arret_min integer NOT NULL CHECK (arret_min BETWEEN 0 AND 30)` (5 par défaut), `exclusion_releves_jours integer NULL CHECK (exclusion_releves_jours > 0)`, `resultat jsonb NOT NULL`, `cree_le timestamptz NOT NULL DEFAULT now()`, `expire_le timestamptz NOT NULL` (`cree_le + 24 h`) ; index sur `expire_le` et sur `compte_id`
- [ ] T002 [P] Créer le paquet `src/bitumap/parcours/__init__.py` (docstring : rôle du module, renvoi à `specs/006-parcours-surveillance/`) et `tests/parcours/__init__.py`
- [ ] T003 [P] Ajouter la purge des parcours expirés dans `src/bitumap/db/purge.py` (`DELETE FROM parcours WHERE expire_le < now()`, compte dans le résultat de `purger()`) et son test dans `tests/parcours/test_purge.py` (parcours de plus de 24 h supprimé, récent conservé ; SC-006)

**Checkpoint**: la migration s'applique sur une base vide (`tests/conftest.py`, fixture `schema`) et la purge fonctionne.

---

## Phase 2: Foundational (prérequis de toutes les stories)

**Purpose**: services externes (adresse, itinéraire) et lecture des points, sans réseau en test.

**⚠️ CRITICAL**: aucune story ne commence avant la fin de cette phase.

- [ ] T004 [P] Écrire `tests/parcours/test_geocodage.py` (respx) : réponse de `https://data.geopf.fr/geocodage/search` simulée ⇒ jusqu'à 5 propositions `{libelle, lon, lat, score}` triées par score ; texte de moins de 3 caractères refusé ; adresse unique de score ≥ 0,7 ⇒ choix automatique possible, sinon propositions (R1, FR-003) ; service en erreur ⇒ `SourceIndisponible`
- [ ] T005 [P] Écrire `tests/parcours/test_itineraire.py` (respx) : appel de `https://data.geopf.fr/navigation/itineraire` (ressource `bdtopo-osrm`, profil `car` pour « voiture », `pedestrian` pour « pied ») ⇒ distance (m), durée (s), géométrie et une portion par étape ; **plus de 15 points intermédiaires ⇒ plusieurs tronçons enchaînés** (fin d'un tronçon = début du suivant, aucun trou ; R2) ; `429` ou `5xx` ⇒ nouvelle tentative avec attente croissante, puis `SourceIndisponible` (R4) ; limiteur : au plus 4 requêtes par seconde (horloge injectée, sans attente réelle)
- [ ] T006 Créer `src/bitumap/parcours/geocodage.py` : `rechercher(texte, client, limite=5) -> list[Adresse]` (`Adresse` : `libelle`, `lon`, `lat`, `score`), URL constante, provenance « IGN Géoplateforme, géocodage (Base Adresse Nationale), Licence Ouverte » ; aucune adresse dans les journaux
- [ ] T007 Créer `src/bitumap/parcours/itineraire.py` : `Limiteur` (4 requêtes par seconde, horloge et attente injectables), `trajet(points, mode, client, limiteur) -> Trajet` (`distance_m`, `duree_s`, `geometrie` en WGS 84, `etapes` : durée et distance par étape) découpé en tronçons de **15 intermédiaires au plus**, nouvelles tentatives sur `429` / `5xx` ; `duree(a, b, mode, …)` pour un seul trajet ; profils `MODES = {"voiture": "car", "pied": "pedestrian"}` ; provenance « IGN Géoplateforme, itinéraire (BD TOPO), Licence Ouverte »
- [ ] T008 [P] Ajouter à `src/bitumap/terrain/points.py` (ou réutiliser) la lecture des points du rapport en vigueur **avec la date du rapport** pour le parcours : `points_en_vigueur(insee)` existe (rang, groupe, désignation, position) ; ajouter la date de production (`stockage.date_rapport`) dans une fonction `rapport_pour_parcours(insee) -> (empreinte, date, points)` ; test dans `tests/parcours/test_points.py` (rapport absent ⇒ `None`)

**Checkpoint**: adresse et itinéraire utilisables hors réseau dans les tests ; points du rapport lus avec leur rang estimé.

---

## Phase 3: User Story 1 - Obtenir une boucle depuis une adresse (Priority: P1) 🎯 MVP

**Goal**: boucle depuis l'adresse, points dans l'ordre du rang tant que la durée maximale tient (trajets, arrêts, retour), non visités listés (FR-001 à FR-007, FR-013, FR-014).

**Independent Test**: rapport figé de Courbevoie, départ « 2 place de l'hôtel de ville », niveaux Critique et Sérieux, voiture, 3 h, itinéraire simulé : points visités dans l'ordre croissant du rang, durée ≤ 3 h retour compris, non visités listés avec leur rang.

### Tests for User Story 1

- [ ] T009 [P] [US1] Écrire `tests/parcours/test_selection.py` (fonctions pures, durées simulées) : visites dans l'ordre croissant du rang (SC-003) ; durée totale (trajets + `arret_min` par point + retour) ≤ `duree_max_min` dans tous les cas (SC-003) ; point qui ferait dépasser ⇒ « non visité » raison `duree`, le suivant est essayé (FR-006) ; préfiltre à vol d'oiseau (distance / vitesse maximale du mode) ⇒ aucun appel pour un candidat impossible (R3) ; arrêt dès que le reste est inférieur au temps d'arrêt ; au plus 60 candidats évalués, les suivants « non visités » raison `limite_candidats` ; aucun point dans les niveaux ⇒ erreur `aucun_point` ; durée trop courte même pour le premier point ⇒ `duree_insuffisante` avec la durée minimale ; tous les points tiennent ⇒ durée restante indiquée ; point inaccessible dans le mode ⇒ raison `inaccessible`
- [ ] T010 [P] [US1] Écrire `tests/parcours/test_api_parcours.py` (client de test, base, S3 simulé, `rapport_courbevoie()`, géocodage et itinéraire simulés) : `GET /parcours/{insee}` ⇒ formulaire avec le nombre de points par niveau, `404` sans rapport ; `GET /parcours/adresses?q=&insee=` ⇒ 5 propositions, `400` texte trop court ; `POST /parcours/{insee}` ⇒ `303` vers `/parcours/resultat/{id}` ; erreurs `400 aucun_point`, `400 duree_insuffisante`, `400 depart_trop_loin` (> 20 km du centre de la commune), `429 quota_parcours` (21e demande du jour), `503 itineraire_indisponible` ; CSRF obligatoire ; sans session ⇒ `401` ; résultat d'un autre compte ⇒ `404` ; l'adresse de départ n'apparaît dans aucun journal (caplog)

### Implementation for User Story 1

- [ ] T011 [US1] Créer `src/bitumap/parcours/selection.py` : `selectionner(depart, candidats, mode, duree_max_s, arret_s, duree) -> Selection` selon R3 (ordre du rang, retour mis en mémoire par candidat, préfiltre à vol d'oiseau avec `VITESSE_MAX_KMH = {"voiture": 70, "pied": 6}`, 60 candidats au plus) ; `Selection` : `visites` (`{ordre, point_id, rang, niveau, designation, lon, lat, duree_cumulee_s, distance_cumulee_m, accessible}`), `non_visites` (`{point_id, rang, niveau, raison}`, `raison` ∈ `duree`, `inaccessible`, `releve_recent`, `limite_candidats`), `duree_restante_s` ; erreurs `AucunPoint`, `DureeInsuffisante(duree_min_s)`
- [ ] T012 [US1] Créer `src/bitumap/parcours/service.py` : `calculer(insee, compte_id, depart, niveaux, mode, duree_max_min, arret_min, exclusion_releves_jours=None) -> uuid` : points du rapport en vigueur filtrés par niveau, départ à moins de 20 km du centre de la commune (`DepartTropLoin`), sélection, **tracé final** de la boucle par `itineraire.trajet` (départ → visites → départ), résumé (distance totale, durée trajets / arrêts / retour, durée restante, nombre de visités et non visités, date du rapport, sources) ; écriture dans `parcours` avec `expire_le = now() + 24 h` ; service indisponible ⇒ `ItineraireIndisponible`, rien d'enregistré (aucun GPX partiel)
- [ ] T013 [US1] Créer `src/bitumap/api/parcours.py` (routeur `/parcours`, `SessionRequise`, `verifier_csrf`) : routes du contrat `GET /parcours/{insee}`, `GET /parcours/adresses`, `POST /parcours/{insee}` (quota `parcours:compte:{id}:{jour}` de 20 avec `quotas.limiter`, code `quota_parcours`), `GET /parcours/resultat/{id}` (seul le compte propriétaire, sinon `404` ; expiré ⇒ `404`) ; entrées bornées (niveaux parmi `P1a` … `P3`, mode, `duree_max_min` 30 à 480, `arret_min` 0 à 30) ; erreurs `{erreur, message}` sans détail technique ; l'inclure dans `src/bitumap/api/application.py`
- [ ] T014 [US1] Créer les gabarits `src/bitumap/api/gabarits/parcours/formulaire.html` (adresse avec propositions, niveaux et nombre de points, mode voiture / à pied seulement — FR-002, durée maximale 3 h par défaut, arrêt 5 min par défaut) et `src/bitumap/api/gabarits/parcours/resultat.html` (résumé, ordre de visite, non visités « pour une prochaine tournée » avec rang et niveau, date du rapport, sources) ; script de saisie d'adresse dans `src/bitumap/api/statique/parcours/parcours.js` (propositions via `/parcours/adresses`, aucun script en ligne : CSP de l'API)
- [ ] T015 [US1] Ajouter dans le rapport un lien « Préparer un parcours de surveillance » vers `/parcours/{insee}` (`src/bitumap/rapport/gabarits/rapport.html.j2`) ; test dans `tests/rapport/test_rendu.py`

**Checkpoint**: un agent connecté obtient une boucle consultable dans le service.

---

## Phase 4: User Story 2 - Télécharger le parcours en GPX (Priority: P1)

**Goal**: GPX 1.1 avec la trace de la boucle et un point de passage par point visité, nommé et dans l'ordre, sans donnée de compte (FR-008, FR-012).

**Independent Test**: le GPX du parcours de la story 1 est valide contre le schéma GPX 1.1 ; les `wpt` sont « Départ » puis « 1 · Critique · … » dans l'ordre ; aucune adresse e-mail ni identifiant de compte.

### Tests for User Story 2

- [ ] T016 [P] [US2] Écrire `tests/parcours/test_gpx.py` : contrôle de la structure GPX 1.1 (aucun validateur XSD n'est installé et le plan exclut toute nouvelle dépendance : écart au plan, validation XSD possible plus tard avec l'accord du mainteneur) : espace de noms `http://www.topografix.com/GPX/1/1`, `version="1.1"` et `creator`, ordre `metadata` / `wpt` / `trk`, `lat` dans [−90, 90] et `lon` dans [−180, 180], éléments `name` / `desc` / `trkseg` / `trkpt` aux bons niveaux ; `wpt` « Départ » puis un par visite, `name` = « {ordre} · {niveau} · {désignation} », `desc` = rang, identifiant, lien vers la fiche ; `trk` = un `trkseg` par tronçon ; `metadata` : commune, date du rapport, méthode, sources et licences (IGN Géoplateforme, IDFM, OpenStreetMap) ; aucune adresse e-mail ni `compte_id` ; caractères spéciaux échappés (« & », « < »)
- [ ] T017 [P] [US2] Compléter `tests/parcours/test_api_parcours.py` : `GET /parcours/resultat/{id}.gpx` ⇒ `application/gpx+xml`, `Content-Disposition: attachment; filename="parcours-{insee}-{date}.gpx"` ; autre compte ou expiré ⇒ `404`

### Implementation for User Story 2

- [ ] T018 [US2] Créer `src/bitumap/parcours/gpx.py` : `produire(parcours) -> bytes` (GPX 1.1, `xml.etree.ElementTree`, UTF-8, aucune donnée de compte ; l'adresse de départ n'y figure que comme point « Départ »)
- [ ] T019 [US2] Ajouter la route `GET /parcours/resultat/{id}.gpx` dans `src/bitumap/api/parcours.py` et le lien de téléchargement dans `resultat.html`

**Checkpoint**: US1 et US2 forment le MVP livrable (PR 1).

---

## Phase 5: User Story 3 - Voir le parcours et la feuille de route (Priority: P2)

**Goal**: carte avec la boucle numérotée et feuille de route imprimable (FR-009, FR-010).

**Independent Test**: la page de résultat montre la carte du rapport avec la boucle et les numéros de visite ; la feuille de route tient sur une page A4 pour une vingtaine de points (aperçu avant impression dans un navigateur).

### Tests for User Story 3

- [ ] T020 [P] [US3] Écrire `tests/parcours/test_carte.py` : la carte SVG contient la trace de la boucle (un `path` dédié) et un numéro par visite placé à la **position projetée** du point (même vérification de position que `test_feux_a_leur_place_sur_la_carte`, LL-017 : aucun `transform` sur les numéros) ; la carte du rapport stocké n'est pas modifiée

### Implementation for User Story 3

- [ ] T021 [US3] Étendre `src/bitumap/rapport/carte_svg.py` : `dessiner(…, parcours=None)` ajoute en surcouche la trace et les numéros de visite (sans changer le rendu existant quand `parcours` est absent) ; l'utiliser dans `resultat.html` avec le contour et les voies du rapport en vigueur
- [ ] T022 [US3] Ajouter la feuille de route dans `resultat.html` : ordre, niveau, désignation, distance cumulée, point inaccessible signalé ; feuille de style d'impression (`@media print` : carte et liste sur A4, navigation masquée)

**Checkpoint**: US3 vérifiée dans un navigateur (carte et aperçu d'impression), conformément à LL-012 et LL-017.

---

## Phase 6: User Story 4 - Ne visiter que les points pas encore relevés (Priority: P3)

**Goal**: exclure les points relevés depuis moins de N jours (FR-011) ; 003 est livrée, l'option est active.

**Independent Test**: avec des relevés récents sur 5 des 21 points, « exclure les points relevés depuis moins de 30 jours » ne retient que les 16 autres ; le résumé indique 5 exclus.

### Tests for User Story 4

- [ ] T023 [P] [US4] Écrire `tests/parcours/test_exclusion_releves.py` (base, relevés déposés par l'API de 003 comme dans `tests/terrain/aides.py`) : points dont le **dernier relevé visible** date de moins de N jours ⇒ non visités raison `releve_recent`, comptés dans le résumé ; relevé retiré ⇒ ignoré ; relevé plus ancien ⇒ point candidat ; option absente ⇒ aucun effet

### Implementation for User Story 4

- [ ] T024 [US4] Implémenter l'exclusion dans `src/bitumap/parcours/service.py` en réutilisant `terrain.depot.releves_de_la_commune` (relevés visibles, dernière version) : date du dernier relevé par point, comparée à `now() - N jours` ; aucune donnée de relevé (auteur, observation) dans le parcours
- [ ] T025 [US4] Ajouter l'option au formulaire (`formulaire.html` : case et nombre de jours, 30 par défaut) et au résumé de `resultat.html` (« N points exclus : relevés depuis moins de N jours »)

**Checkpoint**: les quatre stories fonctionnent ; PR 2.

---

## Phase 7: Polish & sujets transverses

- [ ] T026 [P] Compléter la page « Données personnelles » (`src/bitumap/api/gabarits/confidentialite.html`) : adresse de départ conservée 24 h au plus, jamais journalisée, transmise au service de géocodage de l'IGN ; et le README (feuille de route : 006 en cours, section fonctionnalités)
- [ ] T027 [P] Documenter les routes dans `specs/002-on-demand-report/contracts/http-api.md` (renvoi au contrat de 006) et la table dans le contrat de configuration si un réglage est ajouté (`BITUMAP_` uniquement)
- [ ] T028 Revue de sécurité de la branche (`/security-review`) : accès au résultat limité au compte, CSRF, quota, entrées bornées, aucune adresse dans les journaux, appels externes (URL constantes, `verifier_url`, délais), aucun script en ligne ; corriger les constats
- [ ] T029 Exécuter le quickstart § 2 (`uv run pytest tests/parcours`), puis § 3 en réel sur Courbevoie (voiture 3 h, à pied 2 h) dans un navigateur : durée de calcul (SC-001 < 30 s), carte, aperçu d'impression A4, GPX ouvert dans deux applications (SC-002, par le mainteneur) ; `uv run pytest` complet, `ruff check`, `ruff format --check` ; consigner les mesures dans la PR

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → **Foundational (T004–T008)** → stories.
- **US1 (T009–T015)** : MVP ; dépend de la phase 2.
- **US2 (T016–T019)** : dépend de US1 (parcours enregistré) ; fichiers distincts (`gpx.py`).
- **US3 (T020–T022)** : dépend de US1 ; indépendante de US2.
- **US4 (T023–T025)** : dépend de US1 (`service.py`) ; indépendante de US2 et US3.
- **Polish (T026–T029)** : après les stories ; T026 et T027 à tout moment.

### Parallel Opportunities

```text
T002 T003                 (Setup)
T004 T005 T008            (Foundational : tests et points)
T009 T010                 (tests US1)
T016 T017                 (tests US2)
T020 ‖ T023               (tests US3 et US4, fichiers distincts)
T026 T027                 (Polish)
```

## Implementation Strategy

1. **Setup + Foundational** : table, purge, géocodage et itinéraire testés hors réseau.
2. **MVP = US1 + US2** (les deux P1) : boucle dans l'ordre du rang et GPX ; **PR 1**.
3. **US3 + US4 + Polish** : carte et feuille de route, exclusion des points relevés,
   données personnelles, revue de sécurité, essai réel ; **PR 2**.
4. Mise en service avec l'infrastructure de 002 (phase 7 de 002).
