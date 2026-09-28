---
description: "Tâches d'implémentation du rapport de risque d'orniérage à la demande"
---

# Tasks: Rapport de risque d'orniérage à la demande

**Input**: Documents de conception dans `/specs/002-on-demand-report/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10, R7-bis), data-model.md,
contracts/ (http-api, lot-job, report-bundle, configuration), quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des adaptateurs testés sur données
figées et la non-régression Courbevoie ; la spec définit des critères vérifiables (SC-003,
SC-004, SC-006, SC-010, SC-012).

**Organization**: tâches groupées par user story (US1 à US4 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US4

## Règles communes (rappel du plan et de la constitution)

- Dépendances aux versions de research.md R9 ; **revérifier la dernière version stable** au
  moment de l'ajout (CLAUDE.md) et mettre research.md à jour si elle a changé.
- Aucune donnée personnelle, aucun nom de profil ou chemin de poste dans le dépôt (mémoire
  projet).
- Aucun secret dans le code, `.env` ou les journaux ; lecture via `bitumap.config`.
- Messages d'erreur utilisateur sans détail technique (FR-025).
- Toute requête HTTP sortante : délai maximal, nouvelles tentatives bornées, en-tête
  `User-Agent: bitumap (+https://github.com/aboigues/bitumap)`.
- Chaque source écrit dans le cache sa licence, son URL et sa date d'extraction (principe III).
- Commits sur la branche `002-on-demand-report` uniquement, fichiers nommés explicitement
  (LL-002).

---

## Phase 1: Setup (infrastructure partagée)

**Purpose**: projet Python, outillage, conteneurs, CI

- [X] T001 Créer `pyproject.toml` (nom `bitumap`, `requires-python = ">=3.14"`, dépendances de research.md R9, groupe `dev` : pytest, ruff, respx, moto ; scripts `bitumap-migrer = "bitumap.db.migrer:main"`), le paquet `src/bitumap/__init__.py` et générer `uv.lock` avec `uv lock` (uv ≥ 0.12)
- [X] T002 Configurer Ruff (lint + format, `target-version = "py314"`, longueur 100) et pytest (`testpaths = ["tests"]`, marqueurs `reseau` exclus par défaut) dans `pyproject.toml`
- [X] T003 [P] Créer `docker/api.Dockerfile` et `docker/job.Dockerfile` : construction en deux étapes sur images Chainguard Python 3.14 **épinglées par digest** (research R9-bis), `uv sync --frozen --no-dev --no-cache`, exécution non root sans shell, code en lecture seule, `HEALTHCHECK NONE` pour le job, point d'entrée `uvicorn bitumap.api:app` / `python -m bitumap.lot`
- [X] T004 [P] Créer `compose.yaml` de développement : PostgreSQL (même version majeure que Serverless SQL Database, à vérifier) et serveur S3 simulé (image moto), tous deux épinglés par digest, sans port exposé hors `127.0.0.1`
- [X] T005 [P] Créer `.github/workflows/tests.yml` (job `name: tests` : `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest` avec service PostgreSQL) en respectant les règles de la 001 (permissions minimales, actions `actions/*` épinglées par SHA, `persist-credentials: false`, `runs-on: ubuntu-26.04`) ; vérifier en local avec zizmor et actionlint (CLAUDE.md)
- [X] T006 [P] Ajouter `python` à la matrice de `.github/workflows/codeql.yml` et les écosystèmes `uv` (répertoire `/`) et `docker` (répertoire `/docker`) avec cooldown 7 jours dans `.github/dependabot.yml`
- [X] T007 [P] Compléter `.gitignore` : `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `var/` (sorties locales)
- [X] T089 Corriger l'analyse des images dans `.github/workflows/security.yml` et `.github/workflows/release.yml` (constitution, principe I) : rechercher les fichiers `Dockerfile` **et** `*.Dockerfile` hors `.git/` et `.github/`, construire avec **la racine du dépôt comme contexte** (`docker build -f <fichier> .`), afficher le nom de chaque image analysée ; vérifier sur la PR, dans le journal, que les images `api` et `job` sont bien construites et analysées (un contrôle vert ne suffit pas, LL-003) ; zizmor et actionlint en local

---

## Phase 2: Foundational (prérequis bloquants)

**Purpose**: configuration, base, stockage, territoire, connexion, socle HTTP, adaptateurs

**⚠️ CRITICAL**: aucune user story avant la fin de cette phase

- [X] T008 Implémenter `src/bitumap/config.py` (pydantic-settings) avec **toutes** les variables et valeurs par défaut de `contracts/configuration.md` ; les secrets en `SecretStr`, jamais journalisés
- [X] T009 Écrire `src/bitumap/db/migrations/001_schema.sql` selon data-model.md : tables `compte` (`email` unique, minuscules), `lien_connexion` (clé `empreinte_jeton` SHA-256, `compte_id` **nullable** (compte créé à la première validation), `expire_le = emis_le + 15 min`, `utilise_le` nul), `source_version` (source, portée, date d'extraction courante, rafraîchie le), `alerte_envoyee` (clé, envoyée le : une alerte par mois au plus), `session`, `preuve_antibot` (clé `signature`), `compteur_quota`, `demande` (états `en_file`, `en_cours`, `terminee`, `en_echec` ; étapes `acquisition`, `calcul`, `rapport` ; `tentatives ≤ 2` ; **index unique partiel sur `empreinte` quand `etat` ∈ {en_file, en_cours}**), `demandeur_demande`, `lot` (`nb_demandes ≤ 10`), `cout_ia_jour`, `ia_cache_point` (clé : point, millésimes, modèle, version du prompt ; R7-bis)
- [X] T010 Implémenter `src/bitumap/db/connexion.py` (pool psycopg, transactions) et `src/bitumap/db/migrer.py` (applique les migrations dans l'ordre, table `schema_version`, idempotent)
- [X] T011 [P] Créer `tests/conftest.py` : base PostgreSQL de test (compose), S3 simulé (moto), horloge injectable, client HTTP FastAPI ; marqueur `reseau` pour les tests qui appellent de vraies API
- [X] T012 [P] Implémenter `src/bitumap/stockage.py` : buckets rapports et cache, `ecrire`, `lire`, `existe`, écriture de `rapport.html` **en dernier** (contracts/lot-job.md)
- [X] T013 [P] Implémenter `src/bitumap/territoire/api_geo.py` : validation du format (5 chiffres, sans appel externe), départements `75, 77, 78, 91, 92, 93, 94, 95`, appel API Géo, Paris par `type=arrondissement-municipal` (`75011` → `75111`), contour communal (FR-001 à FR-003)
- [X] T014 [P] Tests `tests/unit/test_territoire.py` : `92400` → Courbevoie, `95000` → 4 communes, `75011` → Paris 11e, `69001` refusé, `9240` refusé, `99999` inexistant (réponses API figées avec respx)
- [X] T015 [P] Implémenter `src/bitumap/courriel.py` : interface d'envoi, implémentation console (local) et Scaleway Transactional Email ; gabarits texte minimaux (FR-028) : lien de connexion, rapport prêt, échec
- [X] T016 Implémenter `src/bitumap/api/__init__.py` (application FastAPI), en-têtes de sécurité de `contracts/http-api.md` (CSP, HSTS, nosniff, Referrer-Policy), gestion d'erreurs sans détail technique, `GET /sante`
- [X] T017 Implémenter `src/bitumap/api/auth.py` : `POST /connexion` (réponse **identique** que le compte existe ou non, FR-006b), `GET /connexion/{jeton}` (jeton 32 octets, seule l'empreinte SHA-256 stockée, usage unique par `UPDATE … WHERE utilise_le IS NULL`, 15 min), session cookie `__Host-session` (`Secure`, `HttpOnly`, `SameSite=Lax`, 7 jours), jeton CSRF vérifié sur chaque `POST`, `POST /deconnexion`, dépendance `session_requise`
- [X] T018 Tests `tests/api/test_auth.py` : lien valide, réutilisé (410), expiré (410), autre appareil accepté, CSRF manquant refusé, réponse identique pour adresse connue et inconnue
- [X] T019 [P] Implémenter `src/bitumap/sources/base.py` : interface d'adaptateur (`acquerir(emprise) → extraction` avec licence, URL, date), client HTTP partagé, cache régional / communal (data-model.md, stockage objet)
- [X] T020 [P] Implémenter `src/bitumap/score/methode.py` (constante `VERSION_METHODE = "1.0"`) et `src/bitumap/lot/empreinte.py` : `sha256(insee | version_methode | trié(source:date_extraction) | modele_ia | version_prompt_ia)` tronquée à 16 caractères (le modèle d'IA fait partie de l'empreinte, principe IV)
- [X] T021 [P] Créer `src/bitumap/journal.py` : structure de `journal.json` (contracts/report-bundle.md), sans aucune donnée personnelle

**Checkpoint**: base migrée, connexion par lien fonctionnelle en local, adaptateurs prêts à écrire

---

## Phase 3: User Story 1 - Obtenir le rapport d'une commune (Priority: P1) 🎯 MVP

**Goal**: code postal → commune → demande → lot → rapport (méthode 1.0) → e-mail

**Independent Test**: quickstart §2 : se connecter, `92400`, demande `en_file`, lancer `python -m bitumap.lot`, rapport Courbevoie produit et servi ; redemande servie depuis le cache ; non-régression SC-003 et SC-004

### Tests pour US1 (à écrire d'abord)

- [X] T022 [P] [US1] Écrire `tools/figer_fixtures.py` et figer dans `tests/fixtures/courbevoie/` les extractions de toutes les sources pour Courbevoie (IDFM, OSM, BD TOPO, altimétrie, îlots de chaleur, orthophotos, Panoramax), plus les attendus extraits de `docs/reference/prototype-courbevoie-v2.html` (points, rangs, priorités)
- [X] T023 [P] [US1] Écrire `tests/adaptateurs/test_sources.py` : chaque adaptateur, sur les extractions figées, produit les champs attendus avec licence, URL et date
- [X] T024 [P] [US1] Écrire `tests/unit/test_facteurs.py` et `tests/unit/test_score.py` (effets de la méthode 1.0, bornes, priorités 20/40/40, déterminisme)
- [X] T025 [P] [US1] Écrire `tests/non_regression/test_courbevoie.py` : **SC-003** (≥ 80 % des P1 du prototype parmi les P1, écarts listés avec leur cause) et **SC-004** (deux exécutions ⇒ classement identique à 100 %)
- [X] T026 [P] [US1] Écrire `tests/lot/test_lot.py` : file vide ⇒ fin < 30 s ; commune sans ligne de bus ⇒ rapport produit indiquant « aucun point à relever » ; deux lots concurrents ne prennent jamais la même demande ; échec d'une commune sans effet sur les autres ; demande rattachée à une demande active ; reprise après lot interrompu (`tentatives < 2`)
- [X] T027 [P] [US1] Écrire `tests/api/test_parcours.py` : parcours du tableau quickstart §2 (hors antibot et quotas, testés en US2)

### Sources (adaptateurs)

- [X] T028 [P] [US1] Implémenter `src/bitumap/sources/idfm.py` : `arrets`, `offre_hebdomadaire_moyenne_hors_vacances` (bus/jour moyen hors vacances, pointe horaire), `referentiel-des-lignes` (**ODbL**) ; portée régionale
- [X] T029 [P] [US1] Implémenter `src/bitumap/sources/osm.py` : extrait Geofabrik Île-de-France lu avec `osmium` : `highway=traffic_signals`, `junction=roundabout`, relations `route=bus`, `surface`, `ref`, ouvrages d'art ; portée régionale
- [X] T030 [P] [US1] Implémenter `src/bitumap/sources/bdtopo.py` : WFS `BDTOPO_V3:troncon_de_route` (`cpx_classement_administratif`, `cpx_gestionnaire`, `cpx_numero`, `importance`, `urbain`) et `BDTOPO_V3:batiment` (hauteurs) ; portée communale
- [X] T031 [P] [US1] Implémenter `src/bitumap/sources/altimetrie.py` : API altimétrie IGN (`ign_rge_alti_wld`), altitudes à ±30 m de chaque point
- [X] T032 [P] [US1] Implémenter `src/bitumap/sources/chaleur.py` : aléa de jour Institut Paris Region (0–16), portée régionale, cache long
- [X] T033 [P] [US1] Implémenter `src/bitumap/sources/ortho.py` : infrarouge couleur (indice de végétation pour les arbres) et vignettes 512×512 px des orthophotos historiques par point
- [X] T034 [P] [US1] Implémenter `src/bitumap/sources/panoramax.py` : recherche STAC par emprise, photo la plus récente à moins de 30 m, **licence relevée photo par photo** (FR-015)

### Points, facteurs, score

- [X] T035 [US1] Implémenter `src/bitumap/points/construction.py` : arrêts desservis dans la commune, carrefours à feux et giratoires traversés par au moins une ligne ; identifiants stables `A{id_arret}`, `F{id nœud OSM}`, `G{id chemin OSM}` (FR-010, FR-016) ; exclusion des points hors commune
- [X] T036 [P] [US1] Implémenter `src/bitumap/facteurs/charge.py` : bus/jour en échelle logarithmique ; carrefour : voie la plus chargée + moitié de la seconde
- [X] T037 [P] [US1] Implémenter `src/bitumap/facteurs/sollicitation.py` : arrêt ×1,0, feu ×0,8, giratoire ×0,7 ; arrêt à moins de 40 m d'un feu ×1,2 ; ≥ 20 bus/h en pointe ×1,1
- [X] T038 [P] [US1] Implémenter `src/bitumap/facteurs/site.py` : pente ≥ 3 % jusqu'à ×1,32 ; béton ou pavés ×0,5 ; pente > 9 % jugée douteuse et ignorée ; ouvrage d'art signalé
- [X] T039 [P] [US1] Implémenter `src/bitumap/facteurs/ensoleillement.py` (méthode 1.0) : heures de soleil direct 8 h–20 h à la mi-juillet (pvlib), ombres des bâtiments BD TOPO et des arbres (infrarouge) ; effet ×0,8 à ×1,2 ; limites documentées
- [X] T040 [P] [US1] Implémenter `src/bitumap/facteurs/chaleur.py` : aléa 0–16 ⇒ ×0,92 à ×1,08 ; « non évalué » si source indisponible
- [X] T041 [US1] Implémenter `src/bitumap/score/combinaison.py` : produit des facteurs, normalisation 0–100, rangs, priorités P1 20 % / P2 40 % / P3 reste (FR-011, FR-012) **figées à ce stade** ; puis application de l'âge de l'enrobé aux P1 (×0,85 si réfection il y a 5 à 12 ans, ×1,05 au-delà de 12 ans, inchangé sous 5 ans) qui ne modifie que le score et le rang **à l'intérieur des P1** : un point ne change jamais de priorité à cause de l'IA (SC-012, principe V) ; test dédié dans `tests/unit/test_score.py`

### IA vision (âge de l'enrobé)

- [X] T042 [P] [US1] Implémenter `src/bitumap/ia/client.py` : client `openai` pointé sur Scaleway Generative APIs, modèle `BITUMAP_IA_MODELE`, sortie contrainte par schéma JSON (période, confiance, justification), délai maximal
- [X] T043 [P] [US1] Implémenter `src/bitumap/ia/budget.py` : **réservation avant chaque appel** dans `cout_ia_jour` et dans le budget du rapport, ajustement après, coût = jetons × tarifs configurés ; plafonds 2 €/rapport et 20 €/jour (FR-024)
- [X] T044 [P] [US1] Implémenter `src/bitumap/ia/cache.py` : cache par point indexé par (point, millésimes d'orthophoto, modèle, version du prompt) dans `ia_cache_point` ; un succès du cache ne coûte rien (R7-bis)
- [X] T045 [US1] Implémenter `src/bitumap/ia/age_enrobe.py` et `src/bitumap/ia/prompts/age_enrobe_v1.txt` : P1 uniquement, 6 millésimes, validation du schéma, réponse invalide ⇒ « non évalué », statut « à confirmer » avec modèle et date, réponse brute écrite dans `ia/{point_id}.json` (FR-014)
- [X] T046 [P] [US1] Écrire `tests/unit/test_ia.py` (respx) : réponse hors schéma ⇒ non évalué ; budget épuisé ⇒ aucun appel ; succès du cache ⇒ aucun appel ; effet borné à ×0,85–×1,05

### Lot

- [X] T047 [US1] Implémenter `src/bitumap/lot/prise_en_charge.py` : requête `FOR UPDATE SKIP LOCKED` de `contracts/lot-job.md`, taille `BITUMAP_LOT_TAILLE`, remise en file des demandes d'un lot de plus de 3 h, report au lendemain si le budget IA est insuffisant
- [X] T048 [US1] Implémenter `src/bitumap/lot/regional.py` : acquisition unique par lot des sources régionales (IDFM, OSM, îlots de chaleur) depuis le cache si à jour ; rafraîchissement au plus une fois par jour, puis mise à jour de la table `source_version` lue par l'API ; mesure de `lot.duree_regionale_s` (FR-007b)
- [X] T049 [US1] Implémenter `src/bitumap/lot/commune.py` : étapes `acquisition` → `calcul` → `rapport` avec mise à jour de `demande.etape`, délai maximal de 30 min, isolement des erreurs, sources indispensables vs optionnelles (contracts/lot-job.md)
- [X] T050 [US1] Implémenter `src/bitumap/lot/__main__.py` : enregistrement du lot, boucle des communes, notifications par e-mail à **chaque** compte rattaché (succès ou échec), codes de sortie 0/1, option `--isoler` (mesure SC-002b)
- [X] T051 [US1] Implémenter `src/bitumap/rapport/rendu.py` et le gabarit de base `src/bitumap/rapport/gabarits/rapport.html.j2` : synthèse, liste classée, fiche, méthode, sources (complétés en US3) ; écriture de `points.geojson`, `sources.json`, `journal.json`, puis `rapport.html`

### API et pages

- [X] T052 [US1] Implémenter `src/bitumap/api/communes.py` : `GET /communes?code_postal=` (session requise, erreurs de `contracts/http-api.md`)
- [X] T053 [US1] Implémenter `src/bitumap/api/demandes.py` : `POST /demandes` (cache valide ⇒ `303` vers le rapport ; **cache valide** = rapport dont l'empreinte correspond aux versions courantes de `source_version` et produit depuis moins de `BITUMAP_CACHE_RAPPORT_JOURS` (30) jours ; demande active de même empreinte ⇒ rattachement sans décompte ; sinon création `en_file`), `GET /demandes`, `GET /demandes/{id}` (position, heure estimée = prochain déclenchement + ⌈position/10⌉ × durée moyenne d'un lot, étape)
- [X] T090 [P] [US1] Écrire `tests/api/test_cache.py` : rapport à jour servi sans nouvelle demande ; rapport de plus de 30 jours ou dont une source a une version plus récente ⇒ nouvelle demande `en_file` ; changement de modèle d'IA ⇒ nouvelle empreinte
- [X] T054 [US1] Implémenter `src/bitumap/api/rapports.py` : `GET /rapports/{insee}/{empreinte}` et `/points.geojson`, session requise, fichier lu dans le stockage privé et renvoyé par l'API, `Cache-Control: private, no-store` (FR-021)
- [X] T055 [US1] Créer les pages `src/bitumap/api/gabarits/` : accueil (e-mail ou code postal), choix de la commune, suivi (rafraîchi toutes les 30 s), mes demandes ; accessibles au clavier et au lecteur d'écran, lisibles sur téléphone

**Checkpoint**: MVP : un utilisateur connecté obtient le rapport de Courbevoie ; SC-003 et SC-004 verts

---

## Phase 4: User Story 2 - Être protégé contre les abus (Priority: P1)

**Goal**: antibot, quotas, budget, suppression de compte, minimisation des données

**Independent Test**: quickstart §3 et `tests/api/test_abus.py` : aucune génération ni aucun e-mail sans preuve valide ou au-delà des quotas (SC-006, SC-010)

- [ ] T056 [P] [US2] Écrire `tests/api/test_abus.py` : preuve absente, invalide ou rejouée ; 6ᵉ demande du jour d'un compte ; 51ᵉ demande globale ; 4ᵉ lien en 1 h pour une adresse, 11ᵉ pour une origine ; réponse identique pour une adresse inconnue ; accès au rapport sans session ; budget IA du jour épuisé
- [ ] T057 [US2] Implémenter `src/bitumap/api/antibot.py` : `GET /altcha/defi` (valable 10 min, clé HMAC du secret `bitumap-altcha-hmac`), vérification avec la bibliothèque `altcha`, enregistrement de la signature dans `preuve_antibot` pour refuser toute réutilisation, purge après 1 h
- [ ] T058 [P] [US2] Intégrer le widget ALTCHA 3.2.3 **auto-hébergé** dans `src/bitumap/api/statique/altcha/` avec empreinte SHA-256 vérifiée par `tools/verifier_altcha.py` ; aucun appel à un CDN (CSP `script-src 'self'`)
- [ ] T059 [US2] Implémenter `src/bitumap/api/quotas.py` : clés de `compteur_quota` (data-model.md, dont `defi:origine:{empreinte_ip_salée}:{heure}` pour 60 défis par heure), incrément atomique, adresse IP **empreinte salée** avec le secret `bitumap-sel-origine` renouvelé chaque jour, conservation ≤ 24 h (FR-026)
- [ ] T060 [US2] Brancher antibot et quotas sur `POST /connexion` et `POST /demandes` dans `src/bitumap/api/auth.py` et `src/bitumap/api/demandes.py`, dans l'ordre de `contracts/http-api.md` ; erreur `budget_ia_epuise`
- [ ] T061 [US2] Implémenter `POST /compte/suppression` dans `src/bitumap/api/compte.py` et la purge dans `src/bitumap/db/purge.py` (comptes inactifs depuis 12 mois, liens, sessions, preuves et compteurs expirés), appelée au début de chaque lot (FR-027)
- [ ] T062 [P] [US2] Créer la page `src/bitumap/api/gabarits/confidentialite.html` (finalité, données conservées, durées, droits, suppression du compte) et l'afficher avant la création du compte (FR-027)

**Checkpoint**: SC-006 et SC-010 verts

---

## Phase 5: User Story 3 - Lire et exploiter le rapport (Priority: P1)

**Goal**: rapport complet du prototype + type de route et gestionnaire, autonome et mobile

**Independent Test**: rapport Courbevoie : toutes les sections de `contracts/report-bundle.md`, filtres par type de route, aucun point sans type de route, lisible hors connexion et sur téléphone

- [ ] T063 [P] [US3] Écrire `tests/unit/test_voirie.py` : boulevard Georges Clemenceau ⇒ `départementale` / `Hauts-de-Seine` / `D9B` / `concordant` ; classement BD TOPO vide ⇒ `communale_presumee` ; référence OSM divergente ⇒ `a_verifier` ; aucune donnée ⇒ `indetermine`
- [X] T064 [US3] Implémenter `src/bitumap/facteurs/voirie.py` : classement ∈ {autoroute, nationale, départementale, communale, communale_presumee, privee, indetermine}, gestionnaire (`cpx_gestionnaire`, sinon la commune), numéro, statut ∈ {concordant, a_verifier, indetermine} ; affiché et filtrable, **sans effet sur le score** en 002 (FR-013)
- [X] T065 [P] [US3] Implémenter `src/bitumap/rapport/carte_svg.py` : contour communal, voies très fréquentées par les bus (épaisseur selon la charge), points colorés par priorité et formés par type, sélection ⇒ fiche
- [X] T066 [US3] Compléter `src/bitumap/rapport/gabarits/rapport.html.j2` : sections 1 à 7 de `contracts/report-bundle.md`, synthèse par priorité, type de point et type de route, filtres, fiche complète (FR-018, FR-019 : provenance mesuré / estimé / IA, « non évalué »), avertissement FR-022, styles et script en ligne, thème clair et sombre, mise en page téléphone
- [ ] T067 [P] [US3] Écrire `tests/rapport/test_rendu.py` : aucune ressource externe chargée (seuls des liens cliquables), sections présentes, 100 % des points avec `route.classement`, sources avec licence, lien et date, résultats IA marqués « à confirmer »
- [ ] T068 [P] [US3] Écrire `tools/echantillon_voirie.py` : tire 50 points au hasard (graine fixe) avec leur type de route, pour la vérification manuelle de SC-005 (≥ 90 % exacts)

**Checkpoint**: rapport équivalent au prototype, enrichi du type de route

---

## Phase 6: User Story 4 - Maîtriser les coûts et suivre le service (Priority: P2)

**Goal**: journal complet, plafonds respectés, choix du modèle vision par mesure

**Independent Test**: quickstart §3 (plafond forcé à 0,01 €) et §5 (évaluation des modèles)

- [ ] T069 [US4] Compléter `src/bitumap/journal.py` et `src/bitumap/lot/__main__.py` : durées par étape, nombre de points, appels, jetons, coût IA, non évalués, avertissements, erreurs (FR-023) ; statistiques du lot en base
- [ ] T070 [US4] Implémenter l'alerte au mainteneur quand le budget quotidien est atteint ou qu'un lot échoue : e-mail à l'adresse `BITUMAP_EMAIL_MAINTENEUR` (valeur fournie par variable OpenTofu ou secret, **jamais versionnée**) et journal structuré lisible dans Cockpit
- [ ] T091 [US4] Implémenter l'**alerte mensuelle** dans `src/bitumap/ia/budget.py` : dès que le coût d'IA cumulé du mois civil (somme de `cout_ia_jour`) atteint `BITUMAP_ALERTE_MENSUELLE_EUR` (5 €), un e-mail au mainteneur, **un seul par mois** (table `alerte_envoyee`) ; alerte seulement, **aucun blocage** (les plafonds FR-024 restent les seuls blocages) ; test dans `tests/unit/test_journal.py`
- [ ] T071 [P] [US4] Écrire `tests/unit/test_journal.py` : plafond de 0,01 € ⇒ rapport produit, P1 « âge non évalué », avertissement, aucune dépense supplémentaire (US4-2)
- [ ] T072 [US4] Implémenter `src/bitumap/ia/evaluer.py` : compare `mistral-medium-3.5-128b`, `mistral-small-3.2-24b-instruct-2506` et `qwen3.8-27b` sur `tests/fixtures/ia/echantillon_30.json` (exactitude de la période, coût réel en jetons, aucun changement de priorité dû à l'IA seule, SC-012) ; rapport de comparaison en Markdown
- [ ] T073 [US4] Constituer avec le mainteneur `tests/fixtures/ia/echantillon_30.json` : 30 points P1 dont la date de réfection est connue (vérité terrain), puis lancer T072 et reporter le modèle retenu dans la configuration et dans `specs/002-on-demand-report/research.md` (R7)

**Checkpoint**: coûts observables et plafonnés, modèle vision choisi sur mesure

---

## Phase 7: Infrastructure, livraison et finitions

- [ ] T074 Étendre `infra/bootstrap/bootstrap.sh` et son README : applications IAM `bitumap-api`, `bitumap-job`, `bitumap-ci` avec politiques minimales (plan, suivi de complexité), clés écrites **directement** dans Secret Manager, jamais affichées ; exécuter **deux fois** (LL-001)
- [ ] T075 [P] Créer `infra/tofu/versions.tf` et `infra/tofu/backend.tf` : OpenTofu 1.12, fournisseur Scaleway 2.83, backend S3 sur le bucket d'état avec `use_lockfile = true`, bloc `encryption` (clé dérivée d'une phrase secrète fournie par variable d'environnement, hors dépôt)
- [ ] T076 [P] Créer `infra/tofu/stockage.tf` : bucket `bitumap-rapports` (privé, versionné) et `bitumap-cache` (privé, expiration 30 jours)
- [ ] T077 [P] Créer `infra/tofu/base.tf` : Serverless SQL Database (sans minimum de vCPU, pour revenir à zéro)
- [ ] T078 [P] Créer `infra/tofu/registre.tf` : espace de noms privé du Container Registry
- [ ] T079 [P] Créer `infra/tofu/secrets.tf` : secrets de `contracts/configuration.md` (valeurs aléatoires générées pour `bitumap-altcha-hmac` et `bitumap-sel-origine`)
- [ ] T080 Créer `infra/tofu/api.tf` : conteneur serverless `min_scale = 0`, `max_scale = 2`, image par digest, références de secrets, variables d'environnement, sonde `/sante`
- [ ] T081 Créer `infra/tofu/job.tf` : `scaleway_job_definition` avec `cron { schedule = "*/15 * * * *", timezone = "Europe/Paris" }`, `timeout = "3h"`, image par digest, références de secrets
- [ ] T082 [P] Créer `infra/tofu/courriel.tf` : domaine Transactional Email (variable `domaine_envoi`) et sorties des enregistrements DNS à créer (SPF, DKIM, DMARC, MX)
- [ ] T092 Mettre en place l'**alerte de facturation Scaleway à 5 € par mois** sur le projet `BITUMAP` (tout le coût : calcul, base, stockage, e-mail, IA) : ressource OpenTofu dans `infra/tofu/alertes.tf` si le fournisseur Scaleway 2.83 la propose (vérifier), sinon procédure pas à pas pour le mainteneur dans `infra/tofu/README.md` (action humaine, console de facturation) ; destinataire non versionné
- [ ] T083 Étendre `.github/workflows/release.yml` : construction des images `api` et `job`, analyse Trivy bloquante, publication vers le registre Scaleway avec le secret GitHub de `bitumap-ci`, digests en sortie de la version ; vérifier avec zizmor et actionlint
- [ ] T084 [P] Mettre à jour `README.md` : file d'attente et lots dans les deux diagrammes, base Serverless SQL, carte SVG (au lieu de MapLibre), connexion par e-mail, rapports réservés
- [ ] T085 [P] Créer `docs/methode/CHANGELOG.md` : méthode 1.0 (facteurs, effets, priorités, limites connues de l'ensoleillement et des îlots de chaleur) et **écart assumé avec le prototype** : les priorités sont figées avant l'âge de l'enrobé, qui ne réordonne qu'à l'intérieur des P1 (le prototype faisait descendre certains P1 en P2)
- [ ] T086 Revue de sécurité de la branche : en-têtes, cookies, CSRF, absence de secret et de donnée personnelle dans les journaux et le dépôt, requêtes SQL paramétrées ; `/security-review` si pertinent
- [ ] T087 Dérouler le quickstart §1 à §4 en local et consigner les résultats (dont SC-002b) dans la description de la PR ; une entrée `LESSON-LEARNED.md` pour chaque incident rencontré
- [ ] T088 Pousser la branche `002-on-demand-report` et ouvrir la PR vers `main`, avec la liste des actions humaines : domaine d'envoi, bootstrap, secret GitHub, ajout de `tests` aux contrôles requis du ruleset, alerte de facturation (T092), `tofu apply`, quickstart §6 dont la **mesure de SC-001** (premier accès à un rapport en cache après 30 min d'inactivité, démarrage à froid du conteneur et de la base compris : < 10 s)

---

## Dependencies & Execution Order

Les tâches T089 à T092, ajoutées après `/speckit-analyze`, sont insérées dans leur phase à
leur place d'exécution ; leur numéro ne suit donc pas l'ordre du fichier.

- **Setup (T001–T007, T089)** → **Foundational (T008–T021)** → user stories. T089 après
  T003 (les Dockerfiles doivent exister).
- **US1 (T022–T055)** : tests T022–T027 en premier ; adaptateurs T028–T034 en parallèle ; T035 → facteurs T036–T040 en parallèle → T041 ; IA T042–T044 en parallèle → T045 ; lot T047 → T048 → T049 → T050 ; T051 après T041 et T045 ; API T052 → T053 → T054 → T055.
- **US2 (T056–T062)** : dépend de T017 (connexion) et T053 (demandes) ; indépendante du pipeline de calcul.
- **US3 (T063–T068)** : dépend de T030 (BD TOPO) et T051 (rendu de base).
- **US1** : T090 avant T053 (tests d'abord).
- **US4 (T069–T073, T091)** : dépend de T043, T045 et T050 ; T073 exige le mainteneur (vérité terrain) ; T091 après T043.
- **Phase 7** : T092 après T075.
- **Phase 7** : T074 avant T079–T081 ; T075 avant les autres fichiers OpenTofu ; T083 après T003 ; T087 et T088 en dernier.

## Parallel Example

```text
# Après la phase 2, en parallèle :
T028 T029 T030 T031 T032 T033 T034      (adaptateurs, fichiers distincts)
T036 T037 T038 T039 T040                (facteurs, après T035)
T042 T043 T044                          (IA)
T056 T058 T062                          (US2, fichiers distincts)
T075 T076 T077 T078 T079 T082           (OpenTofu)
```

## Implementation Strategy

1. **MVP = Setup + Foundational + US1** : un utilisateur connecté obtient le rapport de
   Courbevoie en local, avec SC-003 et SC-004 verts.
2. **US2 avant toute mise en ligne** : aucun déploiement public sans antibot ni quotas
   (principe I).
3. **US3** : rapport complet et type de route.
4. **US4** : coûts observables, puis choix du modèle vision sur mesure (T073 avec le
   mainteneur).
5. **Phase 7** : infrastructure, livraison et mise en ligne par le mainteneur.

La fonctionnalité est volumineuse : elle peut être livrée en **plusieurs PR successives**
(MVP local, protections, rapport complet, infrastructure), chacune verte sur tous les
contrôles requis.
