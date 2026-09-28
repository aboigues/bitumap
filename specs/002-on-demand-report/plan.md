# Implementation Plan: Rapport de risque d'orniérage à la demande

**Branch**: `002-on-demand-report` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-on-demand-report/spec.md`

## Summary

Service web authentifié (lien de connexion par e-mail, antibot ALTCHA, quotas) où l'on
choisit une commune d'Île-de-France par son code postal ; la demande est servie depuis le
cache ou placée en file. Toutes les 15 minutes, un job serverless traite jusqu'à 10 communes
en partageant les données régionales, reproduit la méthode du prototype (version 1.0),
ajoute le type de route et son gestionnaire (BD TOPO + OSM), estime l'âge de l'enrobé des P1
par un modèle vision hébergé en France, produit un rapport HTML autonome et prévient le
demandeur par e-mail. Tout tourne sur Scaleway `fr-par` et revient à zéro au repos.

## Technical Context

**Language/Version**: Python 3.14 (API et job, un seul paquet `bitumap`)

**Primary Dependencies**: FastAPI, uvicorn, pydantic ; geopandas, shapely, pyproj,
rasterio, numpy, pvlib, osmium ; psycopg ; boto3 ; openai (client compatible, pointé sur
Scaleway) ; altcha ; jinja2 ; httpx — versions : [research.md](research.md) R9

**Storage**: Serverless SQL Database (PostgreSQL) pour l'état ; Object Storage pour les
rapports (privé) et le cache des sources (expiration automatique)

**Testing**: pytest ; adaptateurs testés sur extractions figées (Courbevoie) ; non-régression
face au prototype ; respx (HTTP) et moto (S3) ; base PostgreSQL locale en conteneur

**Target Platform**: Scaleway `fr-par` : Serverless Containers (API), Serverless Jobs
(lots, cron), Serverless SQL Database, Object Storage, Secret Manager, Transactional Email,
Generative APIs, Cockpit ; IaC OpenTofu

**Project Type**: service web + job de traitement par lots

**Performance Goals**: rapport en cache < 10 s (SC-001) ; rapport disponible < 45 min en
charge normale (SC-002) ; lot de 10 communes ≥ 30 % plus rapide que 10 générations isolées
(SC-002b)

**Constraints**: 0 € de calcul au repos ; coût IA ≤ 2 €/rapport et ≤ 5 €/jour ; commune
≤ 30 min, lot ≤ 3 h ; e-mail et IA hébergés dans l'UE ; méthode déterministe

**Scale/Scope**: 1 300 communes + 20 arrondissements de Paris ; quelques dizaines de
demandes par jour ; 50 à 1 500 points par commune

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | Statut |
|---|---|---|
| I. Sécurité | connexion par lien à usage unique, antibot, quotas par compte et globaux, CSRF, cookies `__Host-`, secrets dans Secret Manager, IAM limitée au projet, images non root analysées, rapports servis après contrôle de session, nouveau contrôle requis `tests` | ✅ |
| II. Zéro coût au repos | conteneur et job à 0 instance, base serverless à 0 vCPU ; **stockage de la base facturé au repos** | ⚠️ justifié (suivi de complexité) |
| III. Souveraineté | Scaleway `fr-par`, e-mail et IA hébergés en France ; licences par source et par photo ; CI GitHub (hors UE) déjà déclarée, ne voit que du code public | ✅ |
| IV. Méthode reproductible | méthode 1.0 versionnée ; empreinte = commune + méthode + sources ; réponses IA en cache ; test de non-régression Courbevoie | ✅ |
| V. IA encadrée | P1 uniquement, « à confirmer », bornes ×0,85/×1,05, plafonds vérifiés avant chaque appel, journal des coûts, modèle choisi par évaluation | ✅ |
| VI. Terrain | identifiants de points stables (FR-016) ; pas de saisie terrain (003) | ✅ |
| VII. Simplicité | un paquet, trois étapes, adaptateurs testés sur données figées ; une base ajoutée pour un besoin démontré (R1) | ✅ |
| VIII. Retour d'expérience | LESSON-LEARNED à chaque incident ; mesures des lots journalisées | ✅ |
| IX. Agents IA | aucune mise en production par un agent : `tofu apply` et publication d'images déclenchés par le mainteneur | ✅ |

**Post-design (Phase 1)** : aucun nouvel écart.

## Project Structure

### Documentation (this feature)

```text
specs/002-on-demand-report/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-api.md          # routes, entrées, réponses, erreurs
│   ├── lot-job.md           # contrat du job de lot (prise en charge, étapes, sorties)
│   ├── report-bundle.md     # fichiers d'un rapport et schéma des points
│   └── configuration.md     # variables d'environnement et secrets
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml / uv.lock
src/bitumap/
├── config.py                 # réglages (pydantic-settings), plafonds et quotas
├── db/                       # connexion, migrations SQL versionnées, requêtes
├── stockage.py               # accès objet : cache, rapports
├── territoire/               # code postal → communes/arrondissements (API Géo), emprise
├── sources/                  # adaptateurs : idfm, osm, bdtopo, altimetrie, ortho, chaleur, panoramax
├── points/                   # arrêts desservis, carrefours à feux, giratoires ; identifiants stables
├── facteurs/                 # charge, sollicitation, site, voirie, ensoleillement, chaleur, age_enrobe
├── score/                    # méthode 1.0 : combinaison, rangs, priorités
├── ia/                       # client vision, prompt versionné, schéma de réponse, plafonds de coût
├── rapport/                  # gabarits Jinja2, carte SVG, rendu autonome
├── lot/                      # prise en charge, données régionales partagées, boucle des communes
├── api/                      # FastAPI : pages, formulaires, auth, antibot, quotas, suivi, rapports
├── courriel.py               # e-mails de connexion et de notification
└── journal.py                # journal de génération et coûts
tests/
├── unit/                     # facteurs, score, validation, auth, quotas
├── adaptateurs/              # chaque source sur extraction figée
├── api/                      # parcours HTTP (base locale, S3 simulé)
├── non_regression/           # Courbevoie vs prototype (SC-003, SC-004)
└── fixtures/courbevoie/      # extractions figées + attendus
docker/
├── api.Dockerfile            # image minimale, non root, épinglée par digest
└── job.Dockerfile
infra/bootstrap/              # + applications IAM bitumap-ci, bitumap-api, bitumap-job (clés → Secret Manager)
infra/tofu/                   # OpenTofu : base, buckets, secrets, registre, conteneur, job + cron, e-mail
.github/workflows/            # + tests.yml ; codeql : python ; release : images → registre
```

**Structure Decision**: un seul paquet Python partagé par l'API et le job (deux images,
deux points d'entrée), conformément au README ; `infra/tofu/` pour l'infrastructure.
Changements du README : file d'attente et lots dans le schéma d'architecture ; carte SVG au
lieu de MapLibre ; base serverless.

## Complexity Tracking

| Écart | Pourquoi nécessaire | Alternative plus simple écartée parce que |
|---|---|---|
| Base Serverless SQL Database (stockage facturé au repos, principe II) | usage unique des liens et des preuves antibot, quotas concurrents, file avec position, prise en charge exclusive d'une demande par un lot (R1) | fichiers JSON sur stockage objet : pas de transactions, verrous et compteurs à réécrire soi-même ; SQS : ni position ni état ; le coût au repos se limite à quelques Mo de stockage |
| Trois nouvelles applications IAM (`bitumap-ci`, `bitumap-api`, `bitumap-job`) créées par le bootstrap | CI : pousser les images ; API et job : droits d'exécution distincts ; la base serverless s'authentifie par clé IAM | réutiliser `bitumap-tofu` donnerait à la CI et à l'exécution des droits sur toute l'infrastructure (principe I, moindre privilège) ; les créer en OpenTofu exigerait des droits IAM pour `bitumap-tofu` |
