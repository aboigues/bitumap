---
description: "Tâches d'implémentation du socle de sécurité CI"
---

# Tasks: Socle de sécurité CI

**Input**: Documents de conception dans `/specs/001-security-ci-baseline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: inclus pour le validateur d'exceptions (principe VII : « chaque adaptateur testable ») ; les
scénarios d'acceptation des workflows sont validés par les branches pièges du quickstart.

**Organization**: tâches groupées par user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1 à US4 (voir spec.md)

## Règles communes à TOUS les workflows (rappel de research.md R1, R7, R9)

- `permissions: {}` au niveau du workflow ; permissions accordées job par job, au minimum.
- `runs-on: ubuntu-26.04`.
- Actions référencées **uniquement** par SHA complet suivi du tag en commentaire :
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, toujours avec
    `persist-credentials: false`
  - `github/codeql-action/*@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2`
  - `actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0`
- Aucune action tierce hors GitHub ; scanners lancés par `docker run --rm` avec l'image lue
  dans `.github/scanners/<outil>.Dockerfile` (`awk '/^FROM/{print $2}'`), dépôt monté en
  lecture seule quand l'outil le permet, **aucun jeton transmis au conteneur**.
- Déclencheurs autorisés : `pull_request`, `push` (branches: [main]), `schedule`,
  `workflow_dispatch`, `push` de tags `v*.*.*` ; jamais `pull_request_target`.
- `concurrency` par workflow et par ref avec `cancel-in-progress: true` (sauf `release.yml`).
- Aucune expression `${{ ... }}` issue d'un contexte contrôlable par l'utilisateur dans un
  bloc `run:` (passer par `env:`).

---

## Phase 1: Setup (infrastructure partagée)

**Purpose**: arborescence et épinglage des scanners

- [ ] T001 Créer l'arborescence `.github/workflows/`, `.github/scanners/`, `.security/`, `scripts/security/`, `tests/security/fixtures/` selon plan.md
- [ ] T002 [P] Créer `.github/scanners/trivy.Dockerfile` contenant une seule ligne `FROM aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969` précédée d'un commentaire expliquant qu'il sert d'épinglage suivi par Dependabot (research R1)
- [ ] T003 [P] Créer `.github/scanners/gitleaks.Dockerfile` : `FROM zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`
- [ ] T004 [P] Créer `.github/scanners/zizmor.Dockerfile` : `FROM ghcr.io/zizmorcore/zizmor:1.30.1@sha256:a2eb396d886c053073405c7a980f2139ba2248ec172243cfa3841e57196e8101`
- [ ] T005 [P] Ajouter à `.gitignore` (le créer s'il n'existe pas) : `*.sarif`, `__pycache__/`, `*.cdx.json`

---

## Phase 2: Foundational (prérequis bloquants)

**Purpose**: registre d'exceptions et fichiers d'ignorance vides, lus par plusieurs contrôles

**⚠️ CRITICAL**: US1 et US3 lisent ces fichiers

- [ ] T006 Créer `.security/exceptions.toml` avec l'en-tête commenté et l'exemple commenté du contrat `contracts/exceptions-registry.md`, sans aucune `[[exception]]` active
- [ ] T007 [P] Créer `.trivyignore` vide avec un commentaire : « chaque entrée DOIT avoir la forme `ID exp:AAAA-MM-JJ` et une exception active dans .security/exceptions.toml »
- [ ] T008 [P] Créer `.gitleaksignore` vide avec un commentaire équivalent (empreintes Gitleaks), et `.security/allowed-ghsas.txt` vide avec un commentaire équivalent (un GHSA par ligne, exception `dependency-review` active obligatoire)

**Checkpoint**: fondations prêtes

---

## Phase 3: User Story 1 - Une PR dangereuse ne peut pas être fusionnée (Priority: P1) 🎯 MVP

**Goal**: 6 contrôles bloquants sur chaque PR (contracts/required-checks.md)

**Independent Test**: branches pièges `trap/secret`, `trap/dependency`, `trap/iac`, `trap/workflow`, `trap/exception-expired` du quickstart §3 → chacune bloquée ; PR propre → tout vert en < 10 min

### Tests pour US1 (validateur, à écrire en premier et voir échouer)

- [ ] T009 [P] [US1] Créer les jeux de test dans `tests/security/fixtures/` : `valid.toml` (1 exception de 30 j), `empty.toml`, `expired.toml` (`expires` avant la date du test), `too_long.toml` (`expires − created` = 91 j), `missing_field.toml` (sans `owner`), `bad_tool.toml` (`tool = "semgrep"`), `duplicate_id.toml`, `invalid.toml` (TOML mal formé), plus les répertoires `root_orphan/` (`.trivyignore` avec un CVE absent du registre) et `root_exp_mismatch/` (`.trivyignore` dont la date `exp:` diffère de `expires`) et `root_ghsa_orphan/` (`.security/allowed-ghsas.txt` avec un GHSA sans exception active)
- [ ] T010 [US1] Écrire `tests/security/test_check_exceptions.py` (`unittest`, stdlib) : un test par fixture de T009 vérifiant le code retour (0, 1 ou 2) et le message `ERREUR <id|fichier>: …` ; date injectée par `--today` pour rendre les tests reproductibles

### Implémentation US1

- [ ] T011 [US1] Implémenter `scripts/security/check_exceptions.py` (stdlib uniquement, `tomllib`, `argparse`, `datetime`) selon `contracts/exceptions-registry.md` : options `--registry` (défaut `.security/exceptions.toml`), `--root` (défaut `.`), `--today` ; champs obligatoires `id` unique au format `EXC-NNN`, `tool ∈ {trivy, gitleaks, codeql, dependency-review}`, `finding`, `reason` non vide, `owner`, `created` ≤ today, `expires` > `created` et « `expires − created ≤ 90 j` », erreur si `expires ≤ today` ; contrôle croisé `.trivyignore` (ligne `ID exp:DATE` ↔ exception active trivy avec même date), `.gitleaksignore` (empreinte ↔ exception active gitleaks) et `.security/allowed-ghsas.txt` (un GHSA par ligne ↔ exception active dependency-review) ; codes retour 0/1/2 ; faire passer T010
- [ ] T012 [US1] Créer `.github/workflows/security.yml` (`name: security`) : déclencheurs `pull_request`, `push` sur `main`, `schedule` hebdomadaire (lundi 05:17 UTC) et quotidien pour les exceptions (05:47 UTC), `workflow_dispatch` ; job `exceptions` (`permissions: contents: read`) : checkout puis `python3 -m unittest discover -s tests/security` et `python3 scripts/security/check_exceptions.py`
- [ ] T013 [US1] Ajouter à `.github/workflows/security.yml` le job `dependency-review` (`if: github.event_name == 'pull_request'`, `permissions: contents: read, pull-requests: write`) avec `fail-on-severity: high`, `comment-summary-in-pr: on-failure`, et `allow-ghsas` lu depuis `.security/allowed-ghsas.txt` par une étape préalable (lignes non commentées jointes par des virgules, transmises par `outputs`/`env`, jamais interpolées dans `run:`) ; ce fichier est validé par T011
- [ ] T014 [US1] Ajouter à `.github/workflows/security.yml` le job `secrets` (`permissions: contents: read, security-events: write`) : checkout `fetch-depth: 0`, `docker run` de l'image gitleaks (lue dans `.github/scanners/gitleaks.Dockerfile`) avec `git --redact --report-format sarif --report-path gitleaks.sarif --gitleaks-ignore-path .gitleaksignore`, upload SARIF via `github/codeql-action/upload-sarif` (catégorie `gitleaks`, `if: always()`), échec du job si gitleaks retourne ≠ 0
- [ ] T015 [US1] Ajouter à `.github/workflows/security.yml` le job `vulnerabilities-iac` (`permissions: contents: read, security-events: write`) : image trivy lue dans `.github/scanners/trivy.Dockerfile`, base de vulnérabilités téléchargée une seule fois dans un répertoire du runner monté dans les deux passes (pas de cache persistant entre exécutions, par simplicité), passe 1 `fs --scanners vuln,misconfig --format sarif --output trivy.sarif` toutes gravités (non bloquante) puis upload SARIF (catégorie `trivy`) ; passe 2 `fs --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 --ignorefile .trivyignore` bloquante ; passe 3 conditionnelle (constitution, principe I : images analysées à chaque PR) : pour chaque `Dockerfile` trouvé hors de `.github/scanners/`, `docker build` local sans push puis `trivy image --severity HIGH,CRITICAL --exit-code 1 --ignorefile .trivyignore`, sinon message « aucune image à analyser » et succès
- [ ] T016 [US1] Ajouter à `.github/workflows/security.yml` le job `workflows-audit` (`permissions: contents: read, security-events: write`) : image zizmor lue dans `.github/scanners/zizmor.Dockerfile`, `zizmor --persona pedantic --format sarif .github/workflows > zizmor.sarif` puis upload SARIF (catégorie `zizmor`), et seconde exécution `--format plain` bloquante sur **toute** détection des règles `unpinned-uses`, `excessive-permissions`, `template-injection`, `dangerous-triggers`, `artipacked`, quelle que soit la gravité (exception FR-005 au titre de FR-014) ; exécution `--offline`, sans jeton
- [ ] T017 [US1] Créer `.github/workflows/codeql.yml` (`name: codeql`) : déclencheurs `pull_request`, `push` sur `main`, `schedule` hebdomadaire, `workflow_dispatch` ; job `analyze` avec `strategy.matrix.language: [actions]` (commentaire : ajouter `python` avec le premier code applicatif), `permissions: contents: read, security-events: write, actions: read`, `init` avec `queries: security-extended`, puis `analyze` avec `category: /language:${{ matrix.language }}`
- [ ] T018 [US1] Vérifier localement que les noms de checks produits correspondent exactement à `contracts/required-checks.md` (`codeql / analyze (actions)`, `security / dependency-review`, `security / secrets`, `security / vulnerabilities-iac`, `security / workflows-audit`, `security / exceptions`) en fixant `name:` des jobs en conséquence

**Checkpoint**: la PR de la feature affiche les 6 contrôles ; US1 testable avec les branches pièges

---

## Phase 4: User Story 2 - Vulnérabilités découvertes après coup (Priority: P2)

**Goal**: réanalyse hebdomadaire de `main` et PR de mise à jour automatiques, jamais fusionnées automatiquement

**Independent Test**: `workflow_dispatch` de `security` sur `main` → résultats dans Security → Code scanning ; Dependabot visible dans Insights → Dependency graph

- [ ] T019 [P] [US2] **Remplacer** `.github/dependabot.yml` (le modèle actuel issu des PR #3/#4 a `package-ecosystem: ""`, invalide) par une configuration version 2 : écosystème `github-actions` (répertoire `/`) et `docker` (répertoire `/.github/scanners`), `schedule.interval: monthly`, un groupe par écosystème, `open-pull-requests-limit: 5`, libellés `dependencies` et `security` ; commentaire indiquant d'ajouter l'écosystème Python avec le premier code applicatif et l'écosystème `opentofu` (répertoire de l'IaC) avec les premiers fichiers `.tf` (feature 002) ; **aucune** configuration de fusion automatique
- [ ] T020 [US2] Vérifier dans `.github/workflows/security.yml` et `.github/workflows/codeql.yml` que les déclencheurs `schedule` s'exécutent sur la branche par défaut et que les jobs `secrets`, `vulnerabilities-iac`, `workflows-audit` n'ont pas de condition limitant à `pull_request` (FR-007)

**Checkpoint**: surveillance continue active

---

## Phase 5: User Story 3 - Livraison inventoriée et analysée (Priority: P3)

**Goal**: SBOM attaché à chaque version, livraison bloquée si ≥ HIGH

**Independent Test**: tag `v0.0.1` → version créée avec `bitumap-v0.0.1.cdx.json` ; sans Dockerfile applicatif, la livraison réussit

- [ ] T021 [US3] Créer `.github/workflows/release.yml` (`name: release`) déclenché par `push` de tags `v*.*.*` : job `scan` (`contents: read`) Trivy `fs --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 --ignorefile .trivyignore` ; étape conditionnelle scannant l'image si un `Dockerfile` existe à la racine (`docker build` puis `trivy image`), sinon message explicite « aucune image à analyser »
- [ ] T022 [US3] Ajouter à `.github/workflows/release.yml` le job `sbom` (`needs: scan`, `contents: read`) : Trivy `fs --format cyclonedx --output bitumap-${TAG}.cdx.json .` (tag passé par `env:`, jamais interpolé dans `run:`), conservé via `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1`
- [ ] T023 [US3] Ajouter à `.github/workflows/release.yml` le job `publish` (`needs: [scan, sbom]`, seul job avec `contents: write`) : récupère l'artefact via `actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1` et exécute `gh release create "$TAG" "bitumap-${TAG}.cdx.json" --generate-notes --verify-tag` avec `GH_TOKEN: ${{ github.token }}`

**Checkpoint**: livraison outillée

---

## Phase 6: User Story 4 - Signalement et revue des zones sensibles (Priority: P3)

**Goal**: politique de sécurité publiée, revue obligatoire des zones sensibles

**Independent Test**: onglet Security → Policy affiche la politique ; une PR modifiant `.github/` demande la revue de `@aboigues`

- [ ] T024 [P] [US4] Créer `SECURITY.md` en français : versions supportées (`main` et dernière version publiée), signalement **uniquement** via « Report a vulnerability » (avis de sécurité privé GitHub), jamais par issue publique ; première réponse sous 7 jours ; délais de correction visés (critique 7 j, élevée 30 j) ; rappel que les détails d'un incident n'apparaissent pas dans `LESSON-LEARNED.md` (principe VIII)
- [ ] T025 [P] [US4] Créer `.github/CODEOWNERS` attribuant `@aboigues` à : `/.github/`, `/.claude/`, `/CLAUDE.md`, `/.specify/memory/`, `/.security/`, `/SECURITY.md`, `/.trivyignore`, `/.gitleaksignore`, `/scripts/security/`, `/LESSON-LEARNED.md` (data-model.md, « Zone sensible »)

- [ ] T031 [US4] Ajouter à `.github/workflows/security.yml` le job `sensitive-paths` (`if: github.event_name == 'pull_request'`, `permissions: contents: read, pull-requests: write`, **non requis**, informatif) : liste les fichiers modifiés de la PR (`gh pr diff --name-only`, `GH_TOKEN: ${{ github.token }}`) appartenant aux zones de `.github/CODEOWNERS` ; s'il y en a, crée ou met à jour **un seul** commentaire marqué `<!-- bitumap:sensitive-paths -->` listant ces fichiers et rappelant que les workflows exécutés sur une PR sont ceux de la PR (relecture humaine obligatoire du diff) ; aucun contenu de la PR n'est interpolé dans `run:` ; job lu depuis la version de `main` impossible en `pull_request`, d'où son caractère informatif (spec, cas limite « Workflow modifié »)

**Checkpoint**: gouvernance en place

---

## Phase 7: Polish & transverse

- [ ] T026 Exécuter localement `python3 -m unittest discover -s tests/security -v` et `python3 scripts/security/check_exceptions.py` : tout doit passer
- [ ] T027 Exécuter localement zizmor sur `.github/workflows/` si Docker est disponible, sinon noter dans la PR que la validation se fera en CI ; corriger toute détection
- [ ] T028 Relire chaque workflow contre les « Règles communes » en tête de ce fichier (permissions, SHA, `persist-credentials: false`, pas d'interpolation dans `run:`)
- [ ] T029 Mettre à jour `CLAUDE.md` : section « Sécurité CI » listant les 6 contrôles requis et la règle d'ajout d'une exception (registre + fichier d'ignorance dans la même PR)
- [ ] T030 Pousser la branche `001-security-ci-baseline` et ouvrir la PR vers `main` avec, dans la description, la liste des actions humaines post-fusion : ajouter au ruleset les 6 contrôles requis et la règle *code scanning* (CodeQL, zizmor : `high_or_higher` / `errors`) selon `contracts/required-checks.md`, puis dérouler le quickstart §3 (branches pièges) ; relever dans la description la durée de la première exécution complète des contrôles (SC-003 : < 10 min)

---

## Dependencies & Execution Order

- **Setup (T001–T005)** → **Foundational (T006–T008)** → US1.
- **US1 (T009–T018)** : T009 → T010 → T011 → T012 ; T013–T016 modifient le même fichier que T012, donc à la suite ; T017 indépendant de `security.yml` (peut suivre T008) ; T018 en dernier.
- **US2 (T019–T020)** : T019 indépendant dès T004 ; T020 après T012–T017.
- **US3 (T021–T023)** : après T002 et T007 ; séquentiel (même fichier).
- **US4 (T024–T025, T031)** : T024–T025 indépendants dès T001 ; T031 après T012 (même fichier `security.yml`).
- **Polish (T026–T030)** : après toutes les stories.

## Parallel Example

```text
# Après T001 :
T002, T003, T004, T005 (fichiers distincts)
T024, T025 (US4, fichiers distincts)
T019 (US2, dès T004)

# Pendant US1 :
T017 (codeql.yml) en parallèle de T011–T016 (validateur + security.yml)
```

## Implementation Strategy

1. **MVP = US1** : Setup + Foundational + US1 → PR ; les 6 contrôles existent et bloquent.
2. US2 et US4 : quelques fichiers de configuration, livrés dans la même PR.
3. US3 : livraison ; testable dès la fusion via un tag `v0.0.1`.
4. Une seule PR pour la feature (socle cohérent), fusionnée par le mainteneur.
