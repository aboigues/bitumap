# Implementation Plan: Parcours de surveillance

**Branch**: `006-parcours-surveillance` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-parcours-surveillance/spec.md`

## Summary

Depuis le rapport d'une commune, l'agent donne une adresse de départ, des niveaux, un mode
(voiture ou à pied) et une durée maximale. L'API géocode l'adresse (Géoplateforme), prend les
points dans l'ordre du rang tant que la boucle tient dans la durée (étape par étape, avec un
préfiltre à vol d'oiseau), puis calcule le tracé par tronçons de 15 points intermédiaires au
plus (limite de l'API d'itinéraire de l'IGN). Résultat : carte, feuille de route imprimable
et GPX, conservés 24 h.

## Technical Context

**Language/Version**: Python 3.14 (paquet `bitumap`)

**Primary Dependencies**: celles de 002 (FastAPI, httpx, jinja2, psycopg) ; GPX avec la
bibliothèque standard ; **aucune nouvelle dépendance**

**Storage**: table éphémère `parcours` (base de 002), purgée à 24 h

**Testing**: pytest ; géocodage et itinéraire simulés (respx) ; validation du GPX contre le
schéma 1.1 ; essai réel manuel (quickstart § 3)

**Target Platform**: API de 002 (Scaleway Serverless Containers) ; services publics de la
Géoplateforme (géocodage, itinéraire)

**Project Type**: service web (extension de l'API de 002)

**Performance Goals**: parcours de 20 à 30 points en moins de 30 s (SC-001)

**Constraints**: 5 requêtes par seconde vers l'itinéraire (limiteur à 4) ; 15 points
intermédiaires par requête ; aucune donnée personnelle conservée au-delà de 24 h

**Scale/Scope**: 20 parcours par compte et par jour ; 60 candidats évalués au plus

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| **I. Sécurité** | Session et CSRF ; résultat accessible au seul compte qui l'a demandé (`404` sinon) ; quota par compte ; limiteur de débit protégeant le service tiers ; entrées bornées (durée, niveaux, distance du départ) | ✅ |
| **II. Zéro coût au repos** | Aucune ressource nouvelle ; calcul à la demande dans l'API ; services publics gratuits | ✅ |
| **III. Souveraineté** | Géocodage et itinéraire : Géoplateforme IGN, en France, Licence Ouverte ; sources citées dans le GPX et la feuille de route | ✅ |
| **IV. Méthode** | Aucun effet sur le score ; l'ordre de visite reprend le rang du rapport | ✅ |
| **V. IA** | Aucune IA | ✅ |
| **VI. Terrain** | Prépare les tournées de relevés ; exclusion des points déjà relevés (003) | ✅ |
| **VII. Simplicité et tests** | Aucun nouveau service ni dépendance ; services externes simulés en test | ✅ |
| **VIII. Retour d'expérience** | Limite de 15 intermédiaires découverte et documentée en conception (R2) | ✅ |
| **IX. Agents IA** | Branche dédiée, PR, fusion humaine | ✅ |
| Données personnelles | Adresse de départ gardée 24 h au plus, jamais journalisée ; GPX sans donnée de compte ; page « Données personnelles » complétée | ✅ |

**Re-check après la conception (phase 1)** : conforme, aucune exception.

## Project Structure

### Documentation (this feature)

```text
specs/006-parcours-surveillance/
├── plan.md              # ce fichier
├── research.md          # phase 0 : R1 à R8
├── data-model.md        # phase 1 : table parcours, résultat
├── quickstart.md        # phase 1 : tests et essai réel
├── contracts/
│   └── http-api.md      # phase 1 : routes, GPX
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/bitumap/
├── parcours/
│   ├── geocodage.py      # adresses officielles (Géoplateforme)
│   ├── itineraire.py     # appels découpés en tronçons, limiteur, nouvelles tentatives
│   ├── selection.py      # ordre du rang, durée maximale, préfiltre à vol d'oiseau
│   └── gpx.py            # GPX 1.1
├── api/
│   ├── parcours.py       # routes /parcours/…
│   └── gabarits/parcours/ # formulaire, résultat, feuille de route (impression)
├── rapport/carte_svg.py  # tracé de la boucle et numéros de visite en surcouche
├── db/migrations/006_parcours.sql
└── db/purge.py           # + parcours expirés

tests/parcours/           # sélection, tronçons, GPX (schéma), accès, purge
```

**Structure Decision**: module `parcours/` isolant la logique des appels externes et de la
sélection ; routes dans l'API de 002 ; carte SVG existante réutilisée.

## Complexity Tracking

Aucune exception à la constitution.

## Dépendances et ordre

- **Autonome** pour US1 à US3 ; **US4** après 003 (option inactive tant que les relevés
  n'existent pas).
- Mise en service avec l'infrastructure de 002 (phase 7).
