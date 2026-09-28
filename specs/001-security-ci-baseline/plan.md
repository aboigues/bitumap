# Implementation Plan: Socle de sécurité CI

**Branch**: `001-security-ci-baseline` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-security-ci-baseline/spec.md`

## Summary

Mettre en place, avant tout code applicatif, les contrôles de sécurité bloquants exigés par le
principe I : analyse de code (CodeQL), revue des dépendances, recherche de secrets (Gitleaks),
analyse des vulnérabilités et de l'infrastructure (Trivy), audit des workflows (zizmor),
validation des exceptions, SBOM à la livraison, Dependabot, `SECURITY.md` et `CODEOWNERS`.
Choix structurant issu de la recherche (R1) : suite à la compromission de `trivy-action` en
mars 2026, seules les actions maintenues par GitHub sont utilisées (épinglées par SHA) ; les
scanners tiers tournent depuis leur image officielle épinglée par digest, sans jeton exposé.

## Technical Context

**Language/Version**: YAML GitHub Actions ; Python 3 (bibliothèque standard seule, `tomllib`)
pour le validateur d'exceptions

**Primary Dependencies**: `actions/checkout` v7.0.1, `github/codeql-action` v4.38.2,
`actions/dependency-review-action` v5.0.0 (SHA dans [research.md](research.md)) ; images
Trivy 0.74.0, Gitleaks 8.30.1, zizmor 1.30.1 (digests dans research.md)

**Storage**: fichiers du dépôt (`.security/exceptions.toml`) ; résultats dans le tableau
« Code scanning » de GitHub (SARIF)

**Testing**: `unittest` (stdlib) pour le validateur ; branches pièges non fusionnées pour les
scénarios d'acceptation (voir [quickstart.md](quickstart.md))

**Target Platform**: GitHub Actions, runners `ubuntu-26.04`

**Project Type**: configuration CI / outillage de dépôt

**Performance Goals**: verdict d'une PR typique < 10 min (SC-003), jobs en parallèle

**Constraints**: coût nul (dépôt public, runners GitHub gratuits) ; aucune action tierce hors
GitHub ; permissions minimales ; aucune fusion automatique

**Scale/Scope**: 1 dépôt, 1 mainteneur, 3 workflows, ~6 contrôles requis

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | Statut |
|---|---|---|
| I. Sécurité d'abord | Couvre SAST, dépendances, secrets, images/IaC, SBOM, permissions minimales, actions épinglées, SECURITY.md ; blocage critique/élevé | ✅ |
| II. À la demande, zéro coût | Aucun composant permanent ; runners GitHub gratuits (dépôt public) | ✅ |
| III. Souveraineté | CI hébergée par GitHub (hors UE) : déclaré ; ne traite que le code source public, aucune donnée de collectivité ni secret de production | ✅ déclaré |
| IV. Méthode reproductible | Non concerné (pas de score) ; outils épinglés = analyses reproductibles | ✅ |
| V. IA encadrée | Non concerné | ✅ |
| VI. Terrain | Non concerné | ✅ |
| VII. Simplicité et tests | 3 scanners tiers seulement (Trivy couvre vulnérabilités, IaC et SBOM) ; validateur testé en `unittest` sans dépendance | ✅ |
| VIII. Retour d'expérience | Fuite de secret → entrée `LESSON-LEARNED.md` exigée (quickstart) ; l'incident Trivy motive R1 | ✅ |
| IX. Agents IA | Dependabot sans fusion auto ; `CODEOWNERS` sur `.github/`, `.claude/`, `.specify/`, `.security/` ; configuration du ruleset laissée à l'humain | ✅ |

**Post-design (après Phase 1)** : aucun écart ; aucune entrée dans le suivi de complexité.

## Project Structure

### Documentation (this feature)

```text
specs/001-security-ci-baseline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── required-checks.md
│   └── exceptions-registry.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
.github/
├── workflows/
│   ├── codeql.yml          # FR-001 : CodeQL (actions ; python plus tard)
│   ├── security.yml        # FR-002..005, FR-007, FR-014, FR-015 : jobs parallèles
│   └── release.yml         # FR-010, FR-011 : scan bloquant + SBOM + création de la version
├── scanners/
│   ├── trivy.Dockerfile    # FROM aquasec/trivy:0.74.0@sha256:…   (suivi Dependabot)
│   ├── gitleaks.Dockerfile # FROM zricethezav/gitleaks:v8.30.1@sha256:…
│   └── zizmor.Dockerfile   # FROM ghcr.io/zizmorcore/zizmor:1.30.1@sha256:…
├── dependabot.yml          # FR-008 : github-actions + docker, mensuel groupé
└── CODEOWNERS              # FR-017
SECURITY.md                 # FR-016
.security/
└── exceptions.toml         # FR-015 : registre (vide au départ)
.trivyignore                # généré/contrôlé à partir du registre (vide au départ)
.gitleaksignore             # idem
scripts/security/
└── check_exceptions.py     # validateur (stdlib)
tests/security/
├── test_check_exceptions.py
└── fixtures/               # registres TOML valides / expirés / incomplets
```

**Structure Decision**: outillage à la racine du dépôt, sans code applicatif. Les futurs
modules applicatifs (`src/`, `tests/`) s'ajouteront à côté ; seules `codeql.yml` (langage
`python`) et `dependabot.yml` (écosystème Python) devront alors être étendues.

## Complexity Tracking

Aucune violation de la constitution à justifier.
