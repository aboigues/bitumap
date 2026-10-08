---
description: "Tâches d'implémentation de la navigation et de la recherche de communes"
---

# Tasks: Navigation et recherche de communes

**Input**: Documents de conception dans `/specs/008-navigation-communes/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R8), data-model.md,
contracts/http-api.md, contracts/interface.md, quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des tests sans réseau : liste
figée du dépôt, API Géo simulée (respx) pour le code postal. Écrire les tests de chaque
story **avant** son implémentation et vérifier qu'ils échouent.

**Organization**: tâches groupées par user story (US1 à US3 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US3

## Règles communes

- **CSP inchangées** (SC-006) : aucune modification de `EN_TETES_SECURITE`
  (`api/application.py`), de `en_tetes_terrain` (`api/terrain.py`) ni de
  `rendu.csp_du_document` ; aucun script en ligne, aucune ressource tierce ; tout script
  est un fichier de `api/statique/`.
- **Rapport stocké jamais modifié** (R6, FR-015) : le menu est inséré dans la réponse,
  jamais écrit dans le bucket ; aucun effet sur l'empreinte ni le score (principe IV).
- **Aucun appel réseau pendant la frappe ni en test** (FR-005) : la recherche par nom lit
  `territoire/communes_idf.json` ; seul le code postal appelle l'API Géo (R4).
- **Frappes jamais journalisées** (R8) : ni `q` dans un message d'erreur, ni dans
  `evenement`.
- **Partir de LL-030** : pages sans session ⇒ `303` vers `/?motif=session&suite=…` (branche
  `fix/interface-heure-session`) ; rebaser 008 après sa fusion (plan, « Dépendances »).
- Commits sur `008-navigation-communes`, fichiers nommés explicitement (LL-002) ; une PR
  par étape livrable ; jamais de fusion par l'agent (principe IX).

---

## Phase 1: Setup

**Purpose**: liste de référence des communes (R1)

- [X] T001 Écrire `scripts/territoire/liste_communes.py` (exécutable, shebang, bit `100755` : LL-015) : appelle `https://geo.api.gouv.fr/communes?codeRegion=11&fields=nom,code,codeDepartement` et `…&type=arrondissement-municipal&…`, retire `75056`, trie par code INSEE, écrit `src/bitumap/territoire/communes_idf.json` au format de data-model.md (`source`, `url`, `genere_le`, `communes: [[insee, nom, departement], …]`), JSON compact une entrée par ligne pour des diffs lisibles ; refuse d'écrire si moins de 1 200 entrées ou un département hors `75, 77, 78, 91, 92, 93, 94, 95` ; `User-Agent` de `territoire.api_geo.USER_AGENT`
- [X] T002 Lancer T001 et versionner `src/bitumap/territoire/communes_idf.json` (attendu le 2026-10-08 : 1 285 entrées, 20 arrondissements `751xx`) ; vérifier que le fichier est inclus dans le paquet construit (`uv build` puis lister l'archive, ou `pyproject.toml` si une règle d'inclusion manque)

---

## Phase 2: Foundational (prérequis bloquants)

**Purpose**: chargement et recherche, structure de navigation partagée par US1 à US3

- [X] T003 [P] Tests de la liste dans `tests/unit/test_communes_idf.py` : invariants de data-model.md (au moins 1 200 entrées, codes uniques de 5 caractères, jamais `75056`, exactement 20 codes `751xx`, départements d'Île-de-France, `source`/`url`/`genere_le` présents) ; normalisation R3 (« Asnières-sur-Seine » = « asnieres sur seine » ; « L'Haÿ-les-Roses » ; « St-Denis » ⇒ « saint denis » ; « Ste » ⇒ « sainte ») ; classement R3 (début de nom avant mot, avant contenu ; puis ordre alphabétique et département) ; au plus 10 résultats ; FR-016 : « cou » ⇒ propositions, « co » ⇒ `[]`, « us » ⇒ Us (95) seule, « bu » ⇒ `[]` ; alias d'arrondissement (« paris 17 », « paris 17e », « 17e », « 1er ») ; « paris » ⇒ les 20 arrondissements ; homonymes (« Blandy ») ⇒ deux résultats, départements distincts ; **SC-001** : pour chaque entrée, le nom complet la trouve ; nombre minimal de lettres du début du nom pour la trouver parmi 10 : médiane ≤ 3, au moins 99 % en 7 au plus, maximum ≤ 10 (valeurs affichées par `print`)
- [X] T004 Implémenter `src/bitumap/territoire/recherche.py` : chargement unique (`functools.cache`) de `communes_idf.json` via `importlib.resources`, `normaliser(texte)` (NFKD, diacritiques retirés, minuscules, `-`/`'`/`’` et espaces multiples ⇒ un espace, `st`/`ste` en tête de mot ⇒ `saint`/`sainte`), alias des arrondissements, `rechercher(q, limite=10) -> list[Commune]` (réutilise `territoire.api_geo.Commune`), `par_insee(insee) -> Commune | None`, `metadonnees()` ; saisie tronquée à 100 caractères ; exporter dans `src/bitumap/territoire/__init__.py`
- [X] T005 [P] Implémenter `src/bitumap/api/navigation.py` : `ENTREES` (rubrique, libellé, adresse, visibilité `tous|connecte|mainteneur|visiteur`) dans l'ordre de contracts/interface.md ; `menu(session) -> list[Entree]` (réutilise `api.auth.est_mainteneur`) ; type `Fil = list[tuple[str, str | None]]` ; enregistrement des globales `menu` et `est_mainteneur` dans `gabarits.env.globals` (comme `api/terrain.py:26`)
- [X] T006 [P] Styles du menu, du `details` et du fil dans `src/bitumap/api/statique/style.css` : `< 48em` menu replié derrière `summary` « Menu » ; `>= 48em` liste affichée en ligne, `summary` masqué (`details > summary { display: none }` et contenu forcé visible) ; entrée courante soulignée épais (pas la couleur seule, FR-009) ; fil : `ol` en ligne, séparateur « › » en `::before` avec `content: "›" / ""` (non lu) ; cibles tactiles ≥ 44 px ; aucun défilement horizontal à 360 px

**Checkpoint**: `rechercher("courbe")` renvoie Courbevoie ; `menu(None)` renvoie Accueil et Données personnelles.

---

## Phase 3: User Story 1 — Trouver sa commune par son nom (Priority: P1) 🎯 MVP

**Goal**: depuis l'accueil connecté, taper un nom, choisir une commune, demander le rapport, sans code postal.

**Independent Test**: accueil connecté ⇒ saisie « courbe » ⇒ choix ⇒ demande créée pour `92026` (récit 1).

### Tests for User Story 1 ⚠️

- [X] T007 [P] [US1] Tests dans `tests/api/test_recherche_communes.py` : `GET /communes/recherche?q=courbe` (session) ⇒ JSON contenant `{"insee": "92026", "nom": "Courbevoie", "departement": "92"}`, au plus 10, `Cache-Control: private, max-age=3600` ; `q` « co » (2 lettres, aucun nom exact) ou de plus de 100 caractères ⇒ `[]` et `200` ; `q=us` ⇒ Us seule ; `GET /communes?q=co` ⇒ message « Saisissez au moins 3 lettres » ; sans session ⇒ `401` en JSON ; `GET /communes?q=asnieres` ⇒ page contenant « Asnières-sur-Seine (92) » en case radio, anti-robot présent ; `GET /communes?q=paris 17` ⇒ « Paris 17e Arrondissement » ; `GET /communes?q=Lyon` ⇒ message « Le service couvre l'Île-de-France » sans erreur ; `GET /communes?q=92400` ⇒ recherche par code postal (API Géo simulée par respx, résultat identique à 002) ; API Géo en erreur (`500` ou `httpx.ConnectError` simulés) ⇒ `200` avec message invitant à chercher par le nom ; `GET /communes?code_postal=92400` toujours servi (anciens liens) ; `GET /communes?insee=92026` ⇒ une seule commune, cochée ; `GET /communes?insee=69123` ⇒ `404 code_inexistant` ; aucun appel réseau pour une recherche par nom (respx en mode strict) ; `q` absent des journaux (`caplog`)
- [X] T008 [P] [US1] Test de bout en bout dans `tests/api/test_recherche_communes.py` : choix depuis `GET /communes?q=courbe` puis `POST /demandes` avec `insee=92026` (anti-robot simulé comme dans les tests de 002) ⇒ demande créée pour Courbevoie (scénario 5 du récit 1)

### Implementation for User Story 1

- [X] T009 [US1] Route `GET /communes/recherche` dans `src/bitumap/api/demandes.py` (déclarée **avant** toute route `/communes/{…}`) : `SessionRequise`, `q` borné, `territoire.rechercher`, JSON `[{insee, nom, departement}]`, en-tête `Cache-Control: private, max-age=3600`
- [X] T010 [US1] Étendre `GET /communes` dans `src/bitumap/api/demandes.py` : paramètres `q`, `insee`, `code_postal` (conservé) ; 5 chiffres ⇒ `communes_du_code_postal` avec capture de `httpx.HTTPError` ⇒ message « Recherche par code postal indisponible : cherchez par le nom de la commune. » ; sinon `territoire.rechercher` ; `insee` ⇒ `territoire.par_insee` ou `404 code_inexistant` ; aucun résultat ⇒ message FR-007 ; contexte du gabarit : `q`, `communes`, `message`
- [X] T011 [US1] Gabarit partiel `src/bitumap/api/gabarits/_recherche_commune.html` : `<form method="get" action="{{ action }}">`, champ `q` (`autocomplete="off"`, `maxlength="100"`, `data-recherche-communes`, `data-destination="{{ destination }}"`, `aria-describedby` vers une aide « nom de la commune ou code postal »), bouton « Chercher », conteneur de propositions vide `role="listbox"` masqué ; mention de la source de la liste (`metadonnees()` : API Géo, Licence Ouverte 2.0, date) en petit texte (principe III)
- [X] T012 [US1] Accueil connecté dans `src/bitumap/api/gabarits/accueil.html` : remplacer le champ code postal par `_recherche_commune.html` (`action="/communes"`, `destination="/communes?insee="`), libellé « Commune ou code postal (Île-de-France) » ; retirer les liens « Mes demandes · Mon compte » (FR-014, contracts/interface.md)
- [X] T013 [US1] Page de choix `src/bitumap/api/gabarits/communes.html` : titre « Choisir la commune », rappel de la saisie, cases radio inchangées (`name="insee"`, cochée si une seule), message éventuel en `role="status"`, formulaire de recherche à nouveau en tête ; lien « Autre code postal » ⇒ « Autre recherche » (FR-014)
- [X] T014 [US1] Script `src/bitumap/api/statique/communes.js` (contracts/http-api.md) : temporisation 150 ms, appel à partir de 2 caractères (FR-016), `AbortController` pour annuler la requête précédente, `fetch("/communes/recherche?q=…", {credentials: "same-origin"})`, propositions rendues avec `textContent` (jamais `innerHTML`), `role="option"` + `aria-activedescendant`, flèches haut/bas, Entrée, Échap ; choix ⇒ `location.assign(destination + insee)` ; aucune proposition ⇒ « Aucune commune d'Île-de-France ne correspond » ; inclus par `<script src="/statique/communes.js" defer>` dans `_recherche_commune.html`
- [X] T015 [US1] Vérifier qu'aucune route ne masque `/communes/recherche` et que `/statique/communes.js` est servi avec le bon type MIME (test ajouté à `tests/api/test_recherche_communes.py`)

**Checkpoint**: US1 livrable seule (PR possible) : recherche par nom, avec et sans script.

---

## Phase 4: User Story 2 — Menu commun à toutes les pages (Priority: P1)

**Goal**: un menu identique sur toutes les pages, rapport compris, adapté au compte qui consulte ; « Relevés terrain » et « Parcours » mènent à un choix de commune.

**Independent Test**: depuis chaque page, chaque entrée mène à la bonne page ; entrée courante signalée ; « Modération » pour le seul mainteneur (récit 2).

### Tests for User Story 2 ⚠️

- [ ] T016 [P] [US2] Tests dans `tests/api/test_navigation.py` : visiteur (`/`, `/confidentialite`, page d'erreur) ⇒ seulement Accueil et Données personnelles, aucune adresse réservée dans le HTML ; agent ⇒ Accueil, Mes demandes, Relevés terrain, Parcours, Mon compte, **sans** « Modération » ni `/terrain/moderation` dans le HTML ; mainteneur (`BITUMAP_EMAIL_MAINTENEUR`) ⇒ « Modération » en plus ; `aria-current="page"` sur l'entrée de la rubrique de chaque page de contracts/interface.md et une seule fois ; menu dans un `<details>` avec `<summary>Menu</summary>` ; page d'erreur `404` d'un compte connecté ⇒ menu d'agent (R5)
- [ ] T017 [P] [US2] Tests des pages de choix dans `tests/api/test_navigation.py` : `GET /terrain` et `GET /parcours` ⇒ liste des communes à rapport disponible (demande `terminee` récente et empreinte égale à `versions.empreinte_courante`), liens `/terrain/{insee}` ou `/parcours/{insee}` ; demande `terminee` d'empreinte périmée ou plus vieille que `cache_rapport_jours` ⇒ absente ; aucune adresse de compte ni date de demande dans la page (clarification Q1) ; `GET /terrain?q=asnieres` sans rapport ⇒ lien « Demander le rapport » vers `/communes?insee=92004` ; sans session ⇒ `303` vers `/?motif=session&suite=%2Fterrain` ; `/terrain/moderation` et `/terrain/{insee}` inchangées
- [ ] T018 [P] [US2] Tests du rapport dans `tests/api/test_rapport_menu.py` : menu inséré juste après `<body>` ; même CSP qu'avant (`csp_du_document` sur le HTML servi égal à celle du rapport stocké : le fragment ne contient aucun `<script>`) ; aucun `<form>` dans le fragment ; bloc `releves` toujours avant le script du rapport (LL-012, `test_bloc_avant_le_script_qui_le_lit` toujours vert) ; rapport produit par une **version antérieure** du gabarit (HTML figé dans `tests/fixtures/`, sans menu) ⇒ menu présent (LL-011) ; mainteneur ⇒ « Modération », autre compte ⇒ absente (FR-015) ; objet du bucket inchangé après consultation (lecture des octets avant/après)

### Implementation for User Story 2

- [ ] T019 [US2] Gabarit partiel `src/bitumap/api/gabarits/_menu.html` : `<nav aria-label="Menu principal" class="menu"><details><summary>Menu</summary><ul>` entrées de `menu(session)`, `aria-current="page"` si `entree.rubrique == rubrique` ; inclus dans `src/bitumap/api/gabarits/base.html` sous l'en-tête (le bouton « Se déconnecter » reste dans l'en-tête)
- [ ] T020 [US2] Déclarer la rubrique de chaque page (`{% set rubrique = "…" %}` en tête de gabarit, valeurs de contracts/interface.md) dans `src/bitumap/api/gabarits/` : `accueil.html`, `communes.html`, `demandes.html`, `suivi.html`, `compte.html`, `confidentialite.html`, `lien_envoye.html`, `terrain/points.html`, `terrain/saisie.html`, `terrain/moderation.html`, `parcours/formulaire.html`, `parcours/resultat.html` ; vérifier que chaque route passe `session` au contexte (sinon l'ajouter dans `src/bitumap/api/*.py`)
- [ ] T021 [US2] Page d'erreur avec le menu du compte : dans le gestionnaire d'erreurs de `src/bitumap/api/application.py`, passer `session_courante(requete)` au contexte de `erreur.html`, toute exception de lecture de session ⇒ `None` (jamais d'erreur en cascade)
- [ ] T022 [US2] Communes à rapport disponible : fonction `communes_avec_rapport() -> list[Commune]` dans `src/bitumap/api/demandes.py` (ou `src/bitumap/lot/` si plus proche des requêtes existantes) : `SELECT DISTINCT ON (commune_insee) commune_insee, commune_nom, empreinte FROM demande WHERE etat = 'terminee' AND termine_le >= now() - make_interval(days => %s) ORDER BY commune_insee, termine_le DESC`, filtrée par `empreinte == versions.empreinte_courante(insee)`, triée par nom
- [ ] T023 [US2] Gabarit `src/bitumap/api/gabarits/choix_commune.html` (rubrique `terrain` ou `parcours`, titre selon la rubrique) : `_recherche_commune.html` (`action` = page courante, `destination` = `/terrain/` ou `/parcours/`), résultats de `q` : lien vers la page de la commune si rapport disponible, sinon « Demander le rapport » (`/communes?insee=`) ; liste « Communes avec un rapport disponible »
- [ ] T024 [US2] Routes `GET /terrain` (dans `src/bitumap/api/terrain.py`, chemin `""`, déclarée avant `/{insee}`, en-têtes `en_tetes_terrain()`) et `GET /parcours` (dans `src/bitumap/api/parcours.py`, chemin `""`) : `SessionRequise`, `q` facultatif, rendu de `choix_commune.html`
- [ ] T025 [US2] Fragment du rapport `src/bitumap/api/gabarits/rapport_menu.html` : `<style>` en ligne préfixé `.bm-` utilisant les variables du rapport (`--surface`, `--encre`, `--ligne`, `--accent`, thème sombre compris), même `<details>`/`<summary>` que `_menu.html` (partiel réutilisé par `{% include %}` si les classes le permettent), **sans** « Se déconnecter », fil « Accueil › Mes demandes › {commune} » ; aucun `<script>`, aucun `<form>`
- [ ] T026 [US2] Insertion dans `rapport()` de `src/bitumap/api/demandes.py` : rendre `rapport_menu.html` avec la session qui consulte et le nom de la commune (`territoire.par_insee`), insérer juste après la première balise `<body…>` (fonction `_inserer_apres_body`, repli : début du document si absente) **avant** `_inserer_avant_script` ; la CSP reste `csp_du_document(html)` calculée sur le HTML final
- [ ] T027 [US2] Retirer les liens devenus doublons (FR-014) et vérifier que le pied de page garde « Données personnelles » dans `src/bitumap/api/gabarits/base.html`

**Checkpoint**: menu sur toutes les pages et dans le rapport ; `/terrain` et `/parcours` utilisables.

---

## Phase 5: User Story 3 — Fil d'Ariane (Priority: P2)

**Goal**: sur chaque page de deuxième niveau ou plus, un fil d'Ariane conforme à contracts/interface.md.

**Independent Test**: chaque page profonde affiche le chemin attendu ; chaque élément sauf le dernier est un lien (récit 3).

### Tests for User Story 3 ⚠️

- [ ] T028 [P] [US3] Tests dans `tests/api/test_navigation.py` : pour chaque ligne de contracts/interface.md, fil exact (libellés et adresses), dernier élément sans lien avec `aria-current="page"`, `nav aria-label="Fil d'Ariane"` ; accueil sans fil ; page d'erreur ⇒ « Accueil › Erreur » ; saisie d'un relevé ⇒ « Accueil › Relevés terrain › Courbevoie › Point A27418 » avec « Courbevoie » vers `/terrain/92026` ; résultat de parcours ⇒ « … › Parcours › {commune} › Résultat » ; noms échappés (commune contenant `'`)

### Implementation for User Story 3

- [ ] T029 [US3] Gabarit partiel `src/bitumap/api/gabarits/_fil.html` (`<nav aria-label="Fil d'Ariane"><ol>`, dernier élément `<span aria-current="page">`) inclus dans `src/bitumap/api/gabarits/base.html` si `fil` est défini et non vide, et dans `rapport_menu.html`
- [ ] T030 [US3] Fournir `fil` à chaque page selon contracts/interface.md : contexte des routes dans `src/bitumap/api/demandes.py` (choix de commune, demandes, suivi), `src/bitumap/api/terrain.py` (points, saisie, modération, choix), `src/bitumap/api/parcours.py` (choix, formulaire, résultat), `src/bitumap/api/compte.py`, `src/bitumap/api/pages.py` (données personnelles), `src/bitumap/api/application.py` (erreur) ; nom de la commune via `territoire.par_insee` (aucun appel réseau)

**Checkpoint**: les trois récits fonctionnent indépendamment.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Mettre à jour `specs/002-on-demand-report/contracts/http-api.md` (ligne `GET /communes`, renvoi vers `specs/008-navigation-communes/contracts/http-api.md`) et la page « Données personnelles » `src/bitumap/api/gabarits/confidentialite.html` si la mention de la liste des communes y a sa place (source, licence)
- [ ] T032 [P] Documenter la mise à jour annuelle de la liste (`scripts/territoire/liste_communes.py`, relecture du diff, PR) dans `README.md` (section Développement)
- [ ] T033 Suite complète : `uv run pytest -q`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts` ; non-régression Courbevoie verte (`test_sc_005` instable connu : à signaler, pas à masquer)
- [ ] T034 Essai navigateur du quickstart § 3 (points 1 à 6) avec Playwright et émulation mobile 360 px : propositions au clavier, sans script, menu replié/ouvert, rapport (filtres, carte, sélection, fiche, lien de saisie, thèmes clair et sombre), aucune erreur CSP en console ; consigner le résultat dans la PR (LL-007, LL-012, LL-017)
- [ ] T035 Revue de sécurité de la PR (règle de LL-019) : CSP inchangées, échappement de tout texte inséré (nom de commune, saisie), absence de « Modération » pour un agent, aucune frappe journalisée ; résultat dans la description de la PR
- [ ] T036 Tout incident rencontré pendant l'implémentation ⇒ entrée dans `LESSON-LEARNED.md` (principe VIII) ; PR vers `main` avec rappel des actions humaines (nouvelle version, digests : LL-023)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance ; T002 après T001.
- **Foundational (Phase 2)** : après T002 ; bloque toutes les stories.
- **US1 (Phase 3)** : après la phase 2.
- **US2 (Phase 4)** : après la phase 2 ; T023 et T024 réutilisent `_recherche_commune.html` (T011) et `communes.js` (T014) : faire US1 d'abord, ou T011 et T014 en tête de US2.
- **US3 (Phase 5)** : après T019 (`base.html` avec le menu) et T025 (fragment du rapport).
- **Polish (Phase 6)** : après les stories retenues.

### Within Each User Story

- Tests écrits et en échec avant l'implémentation.
- Données (`recherche.py`, `navigation.py`) avant routes, routes avant gabarits.

### Parallel Opportunities

- T003, T005, T006 en parallèle (fichiers distincts) après T002.
- T007 et T008 en parallèle ; T016, T017, T018 en parallèle.
- T031 et T032 en parallèle.

---

## Parallel Example: User Story 2

```bash
# Tests de US2, en parallèle :
Task: "T016 tests du menu par profil dans tests/api/test_navigation.py"
Task: "T018 tests du menu du rapport dans tests/api/test_rapport_menu.py"
# Puis, en parallèle (fichiers distincts) :
Task: "T019 _menu.html + base.html"
Task: "T022 communes_avec_rapport() dans api/demandes.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (liste) puis phase 2 (recherche, navigation de base).
2. Phase 3 (US1) : recherche par nom avec et sans script.
3. **Arrêt et validation** : tests, essai navigateur des points 1 du quickstart § 3, PR.

### Incremental Delivery

1. Liste + recherche + US1 ⇒ PR 1 (répond à l'anomalie 4).
2. US2 (menu, pages de choix, rapport) ⇒ PR 2 (anomalie 1).
3. US3 (fil d'Ariane) + finitions ⇒ PR 3.
4. Mise en service après chaque PR fusionnée : nouvelle version, digests (LL-023).
