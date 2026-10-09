---
description: "Tâches d'implémentation de la progression en pourcentage de la génération"
---

# Tasks: Progression en pourcentage de la génération d'un rapport

**Input**: Documents de conception dans `/specs/009-progression-rapport/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R7), data-model.md,
contracts/progression.md, quickstart.md

**Tests**: inclus. La constitution (principe VII) impose des tests sans réseau : fixtures
figées de Courbevoie pour le calcul, base PostgreSQL locale pour la demande. Écrire les
tests de chaque story **avant** son implémentation et vérifier qu'ils échouent.

**Organization**: tâches groupées par user story (US1 : pourcentage ; US2 : durée
restante) ; la liste « Mes demandes » (FR-012) est rattachée à US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 ou US2

## Règles communes

- **Aucun script, aucun point d'accès nouveau, CSP inchangées** (R6) : affichage par
  gabarits seulement, `meta refresh`.
- **Calcul inchangé** (principe IV) : la fonction d'avancement n'a aucun effet sur les
  points, scores ou rapports ; `avancement=None` par défaut partout.
- **La progression n'interrompt jamais la génération** : toute erreur d'écriture est
  journalisée (`journal.exception`) puis ignorée (contrat §1).
- **Jamais 100** : `avancement` est borné à `[0, 99]` (« `NULL` ou `0 ≤ avancement ≤ 99` »,
  data-model).
- **Heures affichées en heure de Paris** (LL-029) : toute heure passe par le module
  `heure` ; la durée restante est une différence, sans fuseau.

---

## Phase 1: Setup

**Purpose**: aucun outil ni dépendance nouvelle (plan) : sans objet.

---

## Phase 2: Foundational (prérequis de US1 et US2)

**Purpose**: schéma de la demande et conversion pure en pourcentage.

- [ ] T001 Créer la migration `src/bitumap/db/migrations/006_avancement.sql` : colonnes
  `demande.avancement smallint` avec `CHECK (avancement IS NULL OR avancement BETWEEN 0 AND
  99)` et `demande.fin_estimee timestamptz` (nullable) ; remplacer la contrainte
  `demande_etape_check` par `CHECK (etape IN ('acquisition', 'calcul', 'sources', 'points',
  'ia', 'rapport'))` (anciennes valeurs conservées pour les lignes existantes, data-model) ;
  commentaire d'en-tête renvoyant à 009.
- [ ] T002 [P] Tests de la conversion dans `tests/unit/test_progression.py` (sans base) :
  bornes par phase `sources` (0, 5), `points` (5, 20), `ia` (20, 97), `rapport` (97, 99) ;
  `floor(debut + (fin − debut) × fait / total)` ; résultat jamais > 99 ni < 0 ; `total = 0`
  ⇒ début de phase ; phase inconnue refusée (`ValueError`) ; cadence : une écriture au
  changement de phase, au plus une toutes les 5 s dans une phase (horloge injectée), la
  dernière valeur d'une phase écrite au changement suivant.
- [ ] T003 Implémenter `src/bitumap/lot/progression.py` (pur, sans base) : constante
  `BORNES` (contrat §2), `pourcentage(phase, fait, total) -> int`, classe `Progression`
  (constructeur : fonction d'écriture `ecrire(etape, avancement, fin_estimee)`, horloge
  `time.monotonic` et `maintenant` injectables, cadence 5 s) dont l'appel
  `progression(phase, fait, total)` décide d'écrire ; toute exception de `ecrire` est
  journalisée et ignorée. Faire passer T002.
- [ ] T004 Tests en base dans `tests/lot/test_lot.py` (ou `tests/lot/test_progression_base.py`) :
  `prise_en_charge.avancer` écrit `etape`, `avancement` et `fin_estimee` ; ne fait jamais
  reculer `avancement` (`GREATEST`) ; n'écrit rien si `etat <> 'en_cours'` ; `terminer`,
  `echouer`, `reporter` et `reprendre_les_lots_interrompus` remettent `avancement` et
  `fin_estimee` à `NULL` ; la contrainte refuse 100.
- [ ] T005 Ajouter `avancer(demande_id, etape, avancement, fin_estimee)` dans
  `src/bitumap/lot/prise_en_charge.py` (`UPDATE demande SET etape = %s, avancement =
  GREATEST(coalesce(avancement, 0), %s), fin_estimee = %s WHERE id = %s AND etat =
  'en_cours'`) ; remettre `avancement = NULL, fin_estimee = NULL` dans toutes les requêtes
  qui remettent `etape = NULL` (lignes de `reprendre_les_lots_interrompus`, `terminer`,
  `echouer`, `reporter`). Faire passer T004.

**Checkpoint**: schéma migré, conversion et écriture testées.

---

## Phase 3: User Story 1 — Voir le pourcentage avancer (Priority: P1) 🎯 MVP

**Goal**: pourcentage, barre et phase sur la page de suivi, mis à jour toutes les 15 s,
croissant, jamais 100 avant le rapport ; « en cours (N %) » dans « Mes demandes ».

**Independent Test**: générer Courbevoie (fixtures) avec la progression branchée sur une
base locale ; relevés successifs de la demande croissants, phases dans l'ordre ; pages de
suivi et de liste conformes au contrat §3.

### Tests for User Story 1

- [ ] T006 [P] [US1] Test de l'ordre des appels dans
  `tests/non_regression/test_progression_courbevoie.py` : `calculer_commune` sur
  `FournisseurFige(FIXTURES, "92026")` avec une fonction d'avancement qui enregistre ses
  appels ; ordre `("sources", 0, 1)`, `("sources", 1, 1)`, puis `("points", i, n)` pour
  i = 1..n (n = nombre de points), puis `("ia", 0, m)` et `("ia", k, m)` pour k = 1..m
  (m = points P1) quand une analyse IA simulée est fournie ; pourcentages calculés
  croissants ; **résultat identique** (points, scores) avec et sans fonction d'avancement.
- [ ] T007 [P] [US1] Test de `AnalyseurAge` dans `tests/unit/test_ia.py` : avec
  `avancement`, un appel `("ia", 0, m)` puis un appel par point P1 quel que soit le
  résultat (réponse, cache, orthophotos indisponibles, plafond atteint, service en
  échec) ; aucun appel si la liste est vide.
- [ ] T008 [P] [US1] Tests des pages dans `tests/api/test_suivi_progression.py` : demande
  `en_cours` avec `avancement = 42`, `etape = 'ia'` ⇒ « 42 % », « analyse des photos
  aériennes », `<progress max="100" value="42"`, `aria-label`, `content="15"` ; sans
  avancement ⇒ « démarrage », sans `<progress>` ; étape ancienne `calcul` ⇒ « génération
  en cours » ; `en_file` ⇒ affichage et `content="30"` inchangés ; `terminee` ⇒ lien
  « Ouvrir le rapport », jamais « 100 % » ; liste `/demandes` ⇒ « en cours (42 %) » ;
  aucune balise `<script>` ajoutée ; un autre compte ne voit pas la demande (contrôle
  existant).

### Implementation for User Story 1

- [ ] T009 [US1] Ajouter le paramètre `avancement: Callable[[str, int, int], None] | None
  = None` à `calculer_commune` dans `src/bitumap/calcul.py` : `("sources", 0, 1)` au
  début, `("sources", 1, 1)` après les sources globales (juste avant la boucle des
  points), `("points", i, n)` à la fin de chaque itération de la boucle des sources
  ponctuelles ; ne rien appeler pour une commune sans point. Le transmettre à
  `calculer_avec_v1` pour le seul calcul principal (R3).
- [ ] T010 [US1] Ajouter `avancement=None` au constructeur de `AnalyseurAge` dans
  `src/bitumap/ia/age_enrobe.py` : `("ia", 0, m)` avant la boucle de `__call__`,
  `("ia", k, m)` après chaque `_analyser`. Faire passer T006 et T007.
- [ ] T011 [US1] Brancher la progression dans `traiter` de `src/bitumap/lot/commune.py` :
  créer `Progression(ecrire=lambda e, a, f: file.avancer(ident, e, a, f))`, la passer à
  `calcul(...)` et à `AnalyseurAge(..., avancement=progression)` ; supprimer les appels
  `file.etape(ident, "acquisition")` et `file.etape(ident, "calcul")` ; remplacer
  `file.etape(ident, "rapport")` par `progression("rapport", 0, 1)`.
- [ ] T012 [US1] Mettre à jour `src/bitumap/api/gabarits/suivi.html` (contrat §3) :
  `meta refresh` à 15 s pour `en_cours`, 30 s pour `en_file` ; libellés des phases
  (`sources` « lecture des données », `points` « analyse des points », `ia` « analyse des
  photos aériennes », `rapport` « mise en forme du rapport », autre valeur « génération en
  cours », `NULL` « démarrage ») ; « Génération en cours : **N %** — <phase>. » et
  `<progress max="100" value="N" aria-label="Avancement de la génération">N %</progress>`
  quand `demande.avancement` est défini ; tolérer une colonne absente (avant migration).
- [ ] T013 [US1] Afficher « en cours (N %) » dans `src/bitumap/api/gabarits/demandes.html`
  et ajouter `d.avancement` à la requête de `mes_demandes` dans
  `src/bitumap/api/demandes.py`. Faire passer T008.
- [ ] T014 [P] [US1] Style de la barre dans `src/bitumap/api/statique/style.css` : largeur
  pleine, hauteur ≥ 0,75 rem, couleur `var(--accent)`, lisible en thème clair et sombre et
  à 360 px.

**Checkpoint**: US1 complète et testable seule (MVP).

---

## Phase 4: User Story 2 — Savoir combien de temps il reste (Priority: P2)

**Goal**: pendant les analyses par l'IA, « environ N min restantes » ou « moins d'une
minute » ; rien avant.

**Independent Test**: `Progression` avec horloge simulée pendant la phase `ia` ⇒
`fin_estimee` conforme à la formule ; page de suivi avec `fin_estimee` future ⇒ durée
arrondie à la minute supérieure ; passée ou `NULL` ⇒ rien.

### Tests for User Story 2

- [ ] T015 [P] [US2] Tests de `fin_estimee` dans `tests/unit/test_progression.py` : `NULL`
  hors phase `ia` et pour `k = 0` ; pour `k ≥ 1` : maintenant + (durée écoulée depuis
  `("ia", 0, m)` / k) × (m − k) + 15 s (horloges simulées).
- [ ] T016 [P] [US2] Tests d'affichage dans `tests/api/test_suivi_progression.py` :
  `fin_estimee` à maintenant + 3 min 10 s ⇒ « Environ 4 min restantes » ; + 40 s ⇒
  « Moins d'une minute » ; passée ou `NULL` ⇒ aucune ligne de durée.

### Implementation for User Story 2

- [ ] T017 [US2] Calculer `fin_estimee` dans `Progression` (`src/bitumap/lot/progression.py`)
  selon le contrat §2, avec `maintenant` injectable (`datetime.now(UTC)` par défaut).
  Faire passer T015.
- [ ] T018 [US2] Calculer la durée restante en minutes dans `suivi_de`
  (`src/bitumap/api/demandes.py`) : `ceil((fin_estimee − maintenant) / 60 s)`, `None` si
  `fin_estimee` est `NULL` ou passée ; l'afficher dans `suivi.html` (« Environ N min
  restantes. », « Moins d'une minute. » sous 60 s). Faire passer T016.

**Checkpoint**: US1 et US2 fonctionnent ensemble.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T019 [P] Mettre à jour `specs/002-on-demand-report/contracts/lot-job.md` (étapes
  écrites par le job : `sources`, `points`, `ia`, `rapport` ; avancement) et la section
  du README qui décrit le suivi d'une demande, s'il y en a une.
- [ ] T020 Mesurer SC-004 sur Courbevoie (fixtures, IA simulée) : durée de `traiter` avec
  et sans progression branchée sur la base locale, écart < 2 % ; consigner la mesure dans
  la PR.
- [ ] T021 Lancer `scripts/essai/lancer.sh` (port 8001) et vérifier dans un navigateur la
  page de suivi d'une demande en cours (pourcentage, barre, phase, durée restante),
  « Mes demandes », 360 px et thème sombre ; vérifier aussi qu'une page de suivi s'affiche
  avant la migration (colonnes absentes).
- [ ] T022 Suite complète (`uv run pytest -q`), ruff (check et format) ; PR avec actions
  humaines « essai des interfaces par le mainteneur avant fusion » (pages : suivi d'une
  demande en cours, Mes demandes) et rappel : en production après v0.1.3 et report des
  digests (LL-023) ; mesures SC-001 à SC-005 du quickstart §4 à faire sur la première
  génération réelle.

---

## Dependencies & Execution Order

- **Phase 2** : T001 avant T004/T005 ; T002 → T003 ; T004 → T005. T002 et T001 en
  parallèle.
- **US1 (Phase 3)** : dépend de T003 et T005. Tests T006, T007, T008 en parallèle ;
  T009 → T010 → T011 ; T012 → T013 ; T014 indépendant.
- **US2 (Phase 4)** : dépend de US1 (T003, T011, T012). T015 et T016 en parallèle ;
  T017 → T018.
- **Phase 5** : après US1 et US2.

### Parallel Opportunities

```text
Phase 2 : T001 (migration) ∥ T002 (tests de conversion)
US1     : T006 ∥ T007 ∥ T008 (tests), puis T014 (style) ∥ T009 → T010 → T011
US2     : T015 ∥ T016 (tests)
Phase 5 : T019 ∥ T020
```

## Implementation Strategy

1. **MVP** : Phase 2 puis US1 (T001–T014) : pourcentage, barre, phase, liste ; utilisable
   seul.
2. **Incrément** : US2 (T015–T018) : durée restante.
3. **Finition** : T019–T022, une seule PR pour la fonctionnalité (petite taille), essai
   du mainteneur avant fusion.
