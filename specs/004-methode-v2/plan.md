# Implementation Plan: Méthode v2 (ensoleillement, chaleur, poids lourds)

**Branch**: `004-methode-v2` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-methode-v2/spec.md`

## Summary

La méthode 2.0 remplace les approximations de la 1.2 par des mesures : ensoleillement sur
les hauteurs LiDAR HD de l'IGN (bâti, arbres, ouvrages et relief réels) et la course du
soleil de juin à août ; indicateurs de chaleur (température de surface de l'été,
minéralisation, contexte urbain) **évalués un par un** sur les relevés de 003
et retenus seulement s'ils aident ; effet poids lourds fondé sur les seuls comptages
publiés. Chaque changement de niveau par rapport à la 1.2 porte sa raison. La 2.0 est
développée derrière un réglage (`BITUMAP_METHODE`) et mise en service par le mainteneur
après validation sur au moins 100 relevés dans 3 communes.

## Technical Context

**Language/Version**: Python 3.14 (paquet `bitumap`)

**Primary Dependencies**: celles de 002 (rasterio, numpy, geopandas, shapely, pvlib, httpx) ;
**aucune nouvelle dépendance prévue** (lecture des dalles GeoTIFF et des scènes par
rasterio) — à confirmer en développement ; climatiseurs (DPE) écartés de la 2.0
(research R4, décision du mainteneur du 2026-09-30)

**Storage**: bucket de cache de 002 (dalles LiDAR, température de surface par été,
comptages, données quotidiennes) ; aucune table nouvelle

**Testing**: pytest ; fixtures de Courbevoie complétées (`tools/figer_fixtures.py`) ; test de
stabilité et de non-régression adapté (chaque changement de niveau expliqué) ; outil
d'évaluation testé sur des relevés synthétiques

**Target Platform**: Scaleway `fr-par` (job de lot de 002)

**Project Type**: évolution de la méthode de calcul du job de lot et du rendu du rapport

**Performance Goals**: rapport v2 en moins de 2 × la durée d'un rapport 1.2 (SC-005)

**Constraints**: données ouvertes et gratuites ; une source hors UE déclarée (USGS) ;
déterministe et reproductible ; mise en service conditionnée à 003

**Scale/Scope**: toutes les communes d'Île-de-France ; 10 à 20 dalles LiDAR par commune ;
une scène composite de température par été et par commune

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| **I. Sécurité** | Aucune nouvelle surface exposée : sources lues par le job (HTTPS, sans secret sauf si un portail l'impose) ; données mises en cache dans le bucket privé ; contrôles CI inchangés | ✅ |
| **II. Zéro coût au repos** | Aucune ressource nouvelle ; cache à expiration | ✅ |
| **III. Souveraineté** | Sources ouvertes. **Hors UE déclaré** : température de surface Landsat distribuée par l'USGS (seule une emprise est transmise ; déclarée ici et dans le rapport). **Nouvelles sources** au-delà de la liste « V1 » du principe III (IGN LiDAR HD, USGS, ADEME, Météo-France, départements) : ouvertes, conformes à l'esprit ; **amendement MINEUR proposé** pour compléter la liste (PR humaine, CODEOWNERS) | ⚠️ amendement à proposer |
| **IV. Méthode reproductible** | Version 2.0, entrée détaillée du journal ; nouvelles sources versionnées dans l'empreinte ; déterminisme testé (SC-006) ; chaque facteur affiché et expliqué | ✅ |
| **V. IA encadrée** | Inchangée (âge de l'enrobé des P1, bornes, « à confirmer ») | ✅ |
| **VI. Terrain** | La validation repose sur les relevés de 003 ; le constaté reste distinct | ✅ |
| **VII. Simplicité et tests** | Pas de nouveau service ; non-régression Courbevoie adaptée : chaque changement de niveau 1.2 → 2.0 expliqué (R8) ; nouvelles sources derrière des adaptateurs testés sur fixtures | ✅ |
| **VIII. Retour d'expérience** | Leçons 1.2 (issue #18) prises en compte ; test #18 conservé | ✅ |
| **IX. Agents IA** | Branche dédiée, PR, fusion et **mise en service** humaines | ✅ |

**Re-check après la conception (phase 1)** : conforme, sous réserve de l'amendement du
principe III (liste des sources), à soumettre par le mainteneur avant la mise en service.

## Project Structure

### Documentation (this feature)

```text
specs/004-methode-v2/
├── plan.md              # ce fichier
├── research.md          # phase 0 : R1 à R8
├── data-model.md        # phase 1 : champs du rapport, cache des sources
├── quickstart.md        # phase 1 : calcul, données manquantes, validation
├── contracts/
│   └── methode-v2.md    # phase 1 : rapport, outil d'évaluation, configuration
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/bitumap/
├── sources/
│   ├── lidar.py            # dalles MNS/MNT LiDAR HD (IGN), cache
│   ├── temperature.py      # température de surface d'un été (USGS), médiane sans nuage
│   ├── comptages.py        # poids lourds : départements + réseau national
│   └── meteo.py            # données quotidiennes (Météo-France), partagé avec 007
├── facteurs/
│   ├── ensoleillement.py   # v2 : grille LiDAR, période chaude, cause d'ombre (1.2 en repli)
│   ├── chaleur.py          # candidats v2 (surface, minéralisation, contexte)
│   └── poids_lourds.py     # effet borné, « non évalué » sans comptage
├── score/
│   ├── methode.py          # VERSION_METHODE 2.0, sélection par BITUMAP_METHODE
│   └── comparaison.py      # niveau 1.2 et raison du changement (R6)
├── methode/evaluer.py      # outil d'évaluation sur les relevés de 003 (R7)
└── rapport/                # fiche, synthèse et section méthode v2

tests/
├── adaptateurs/            # nouvelles sources sur fixtures
├── unit/                   # facteurs v2, cause d'ombre, effet poids lourds, comparaison
└── non_regression/         # Courbevoie : stabilité, changements expliqués, issue #18
```

**Structure Decision**: même paquet et même pipeline (acquisition → calcul → rapport) ; une
source par adaptateur (principe VII) ; la 1.2 reste disponible (repli et comparaison).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Deux méthodes calculées dans le même lot (1.2 et 2.0) | FR-012, SC-004 : expliquer chaque changement de niveau ; non-régression du principe VII | Relire le dernier rapport 1.x : souvent absent ou expiré |
| Source hors UE (USGS) | Seule source ouverte de température de surface à 30–100 m déjà calculée | Sentinel-3 : 1 km, inutile à l'échelle d'une rue ; recalcul du niveau 1 : complexité non justifiée avant que l'indicateur ait prouvé son apport |

## Dépendances et ordre

- **Développement** : possible avant 003 (fixtures, relevés synthétiques pour l'outil).
- **Mise en service** : après 003 en service et une campagne d'au moins 100 relevés dans
  3 communes ; amendement du principe III (liste des sources) fusionné.
- **Partagé avec 007** : `sources/meteo.py` (données quotidiennes, été de référence).
- **À inventorier au développement** : comptages poids lourds publiés par les sept autres
  départements d'Île-de-France.
