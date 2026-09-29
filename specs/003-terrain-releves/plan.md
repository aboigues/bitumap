# Implementation Plan: Relevés terrain

**Branch**: `003-terrain-releves` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-terrain-releves/spec.md`

## Summary

Les agents saisissent sur téléphone, même hors réseau, des relevés rattachés aux points
stables d'un rapport (niveau d'orniérage constaté, mesure, observation, année de réfection,
photos). Les relevés vivent dans la base de 002 (versions, jamais écrasés) et les photos
dans un bucket privé versionné, visibles par leur seul auteur et le mainteneur. À chaque
consultation, l'API insère le « constaté » dans le rapport servi, sans le régénérer ni
toucher au score. Export tableur, SIG et échantillon de réfection pour l'évaluation du
modèle d'IA (002, T073).

Clarifications du 2026-09-29 intégrées : auteur en pseudonyme + domaine (R6), repères des
niveaux avec contrôle de cohérence non bloquant (R11), photos conservées sans limite (R12).

## Technical Context

**Language/Version**: Python 3.14 (paquet `bitumap` de 002) ; JavaScript du navigateur sans
dépendance ni outil de construction pour les pages de terrain

**Primary Dependencies**: celles de 002 (FastAPI, jinja2, psycopg, boto3, Pillow) ; **aucune
nouvelle dépendance** (réencodage et contrôle des images avec Pillow, déjà présent)

**Storage**: base PostgreSQL serverless de 002 (migration `003_releves.sql`) ; nouveau bucket
privé et versionné `bitumap-terrain` (photos), préfixe `quarantaine/` expiré en 1 jour

**Testing**: pytest ; base locale (compose) ; stockage simulé (moto, dont formulaire d'envoi
présigné) ; images de test avec et sans métadonnées ; parcours sur téléphone validé à la
main (quickstart § 2–3)

**Target Platform**: Scaleway `fr-par` (Serverless Containers, Serverless SQL Database,
Object Storage) ; navigateurs de téléphone récents (Safari iOS, Chrome Android)

**Project Type**: service web (extension de l'API de 002)

**Performance Goals**: relevé visible dans le rapport moins d'une minute après l'envoi
(SC-002) ; saisie complète avec deux photos en moins de 2 minutes (SC-001)

**Constraints**: 0 € au repos (hors stockage des photos, plafonné) ; photos jamais
publiques ; aucune métadonnée d'appareil conservée ; saisie possible hors réseau ; rapport
stocké jamais modifié

**Scale/Scope**: quelques centaines de relevés par commune ; 5 photos au plus par relevé ;
plafond global de stockage des photos (20 Go au départ)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| **I. Sécurité d'abord** | Session et CSRF sur toutes les routes ; photos servies seulement à l'auteur et au mainteneur (`404` sinon, sans fuite d'existence) ; formulaire d'envoi présigné court (5 min), taille et type bornés par la politique, contrôle du contenu réel et réencodage côté serveur ; quotas par compte et plafond global de stockage (« denial of wallet ») ; élargissements de CSP limités aux pages de terrain (`connect-src` vers le seul bucket, géolocalisation `self`) ; CodeQL et contrôles de 001 inchangés | ✅ |
| **II. Zéro coût au repos** | Aucune ressource nouvelle facturée au repos, hormis le stockage des photos, plafonné et alerté | ✅ |
| **III. Souveraineté** | Relevés et photos en France, projet `BITUMAP` ; aucun service tiers ; aucune nouvelle source externe | ✅ |
| **IV. Méthode reproductible** | Les relevés ne modifient jamais score, rang ni niveau (couche distincte, test SC-004) ; pas de changement de version de méthode | ✅ |
| **V. IA encadrée** | Aucune IA sur les photos de relevés en 003 | ✅ |
| **VI. Extensible par le terrain** | C'est l'objet même : relevés rattachés aux identifiants stables, versionnés, « constaté » distinct de « estimé » ; saisie = phase 2 prévue par le principe | ✅ |
| **VII. Simplicité et tests** | Pas de nouveau service ni de nouvelle dépendance ; tests sur base et stockage simulés ; **écart** : pages de terrain avec script client (stockage local, envoi différé), voir *Complexity Tracking* | ⚠️ justifié |
| **VIII. Retour d'expérience** | Point de vigilance trouvé en conception (CSP d'un rapport en cache après modification du script, R2) : correctif et test prévus ; entrée `LESSON-LEARNED.md` si l'incident se produit | ✅ |
| **IX. Agents IA** | Branche dédiée, PR, fusion humaine | ✅ |
| Données personnelles | Photos non diffusées (auteur et mainteneur) ; auteur affiché sous pseudonyme + domaine, adresse visible du seul mainteneur (R6, validé le 2026-09-29) ; photos conservées sans limite (décision du mainteneur), justification sur la page « Données personnelles » ; anonymisation à la suppression du compte ; page « Données personnelles » de 002 complétée | ✅ |

**Re-check après la conception (phase 1)** : conforme. Le contrat de 002 prévoyait « pas
d'application JavaScript lourde ; seul script client : ALTCHA » ; 003 ajoute un script de
saisie limité aux pages `/terrain/…`, sans dépendance, justifié ci-dessous.

## Project Structure

### Documentation (this feature)

```text
specs/003-terrain-releves/
├── plan.md              # ce fichier
├── research.md          # phase 0 : décisions R1 à R12
├── data-model.md        # phase 1 : tables et transitions
├── quickstart.md        # phase 1 : validation de bout en bout
├── contracts/
│   └── http-api.md      # phase 1 : routes de terrain, photos, export, modération
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/bitumap/
├── terrain/
│   ├── depot.py            # relevés, versions, retraits, dernier relevé par point
│   ├── photos.py           # formulaire présigné, contrôle, réencodage, retrait RGPD
│   ├── export.py           # CSV, GeoJSON, échantillon de réfection
│   └── pseudonyme.py       # « agent XXXX · domaine » (R6)
├── api/
│   ├── terrain.py          # routes /terrain/… (contrats)
│   ├── demandes.py         # rapport servi : insertion du bloc « releves », CSP calculée (R2)
│   ├── gabarits/terrain/   # liste des points, fiche de saisie, modération
│   └── statique/terrain/   # terrain.js (stockage local, envoi différé), manifeste
├── rapport/
│   ├── interactions.js     # section « Constaté », marqueurs, filtres, synthèse
│   └── gabarits/rapport.html.j2
├── db/migrations/003_releves.sql
└── config.py               # BITUMAP_BUCKET_TERRAIN, BITUMAP_PHOTOS_MAX_GO, quotas

tests/
├── terrain/                # dépôt, photos (métadonnées, contenu), export, pseudonyme
└── api/test_rapport_releves.py   # insertion dans le rapport, score inchangé, CSP
```

Infrastructure (OpenTofu, avec la phase 7 de 002) : bucket `bitumap-terrain` versionné,
règle d'expiration du préfixe `quarantaine/`, règle CORS limitée à l'origine du service
pour l'envoi présigné, droits de l'application `bitumap-api` (lecture, écriture, suppression
de versions).

**Structure Decision**: extension du paquet unique `bitumap` et de l'API de 002 ; un module
`terrain/` isole la logique métier des routes, comme `lot/` et `rapport/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Script client de saisie (stockage local, envoi différé, redimensionnement des photos) | FR-004 et SC-003 : saisie hors réseau sans perte ; R4 : photos réduites sur le téléphone, la limite de taille des requêtes des conteneurs n'étant pas documentée | Formulaires HTML seuls : toute saisie hors réseau serait perdue ; application native : installation, deux plateformes, hors principe VII |
| Élargissement de CSP sur les pages de terrain (`connect-src` vers le bucket, `geolocation=(self)`) | Envoi direct des photos au stockage (R4) ; position de saisie (R9) | Envoi via l'API : limite de taille inconnue ; les autres pages et le rapport gardent la CSP stricte |

## Dépendances et ordre

- **Avant la mise en service** : infrastructure de 002 (phase 7) et bucket `bitumap-terrain`.
- **Débloque** : validation de 004 (≥ 100 relevés dans 3 communes), US4 de 006 (points déjà
  relevés), calage du seuil de 007, échantillon de T073 (002).
- **Clarifications du 2026-09-29** intégrées : pseudonyme + domaine (R6), repères des niveaux (FR-005b : avertissement à la saisie si la mesure contredit le niveau), photos sans limite de durée.
