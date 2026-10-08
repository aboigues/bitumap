# Implementation Plan: Navigation et recherche de communes

**Branch**: `008-navigation-communes` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-navigation-communes/spec.md`

## Summary

Un menu commun (Accueil, Mes demandes, Relevés terrain, Parcours, Mon compte, Modération
pour le mainteneur) et un fil d'Ariane sur toutes les pages, rapport compris ; une
recherche de commune par son nom sur une liste des 1 285 communes et arrondissements
d'Île-de-France intégrée au paquet. La correspondance est faite par l'API (une seule
implémentation, avec et sans script) ; le code postal garde la recherche actuelle. Le menu
est ajouté au rapport **à chaque service**, sans script ni formulaire, ce qui couvre les
rapports en cache sans toucher au stockage ni à la CSP. Aucune table, aucune dépendance,
aucune ressource nouvelle.

## Technical Context

**Language/Version**: Python 3.14 (paquet `bitumap`) ; JavaScript du navigateur sans
outillage (un fichier statique, comme `terrain.js`)

**Primary Dependencies**: celles de 002 (FastAPI, jinja2, httpx, psycopg) ; normalisation
par `unicodedata` (bibliothèque standard) ; **aucune nouvelle dépendance**

**Storage**: liste de référence versionnée `territoire/communes_idf.json` (≈ 36 Ko) ;
lecture de la table `demande` existante (R7) ; aucune migration

**Testing**: pytest ; liste figée du dépôt (aucun réseau) ; rapport produit par une version
antérieure du gabarit (LL-011) ; essai navigateur et lecteur d'écran (quickstart § 3)

**Target Platform**: API de 002 (Scaleway Serverless Containers), navigateurs de bureau et
téléphones (360 px)

**Project Type**: service web (extension de l'API de 002)

**Performance Goals**: propositions en moins de 0,3 s après une frappe (SC-002) ;
correspondance en mémoire < 1 ms pour 1 285 entrées

**Constraints**: CSP des pages et du rapport inchangées (SC-006) ; aucun appel tiers
pendant la frappe ; menu utilisable sans script ; rapport stocké jamais modifié

**Scale/Scope**: 1 285 communes ; quelques dizaines de communes avec rapport (V1) ;
environ 15 gabarits touchés

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| **I. Sécurité** | Session requise sur toutes les routes nouvelles ; aucune CSP affaiblie (pages : `script-src 'self'` suffit ; rapport : ni script ni formulaire ajoutés, `form-action 'none'` gardé) ; « Modération » rendue pour le seul mainteneur, la route reste protégée ; saisie bornée à 100 caractères ; aucune donnée de compte dans la liste des communes disponibles ; contenu inséré dans le rapport rendu par jinja2 avec échappement | ✅ |
| **II. Zéro coût au repos** | Aucune ressource ; liste dans l'image ; calcul en mémoire | ✅ |
| **III. Souveraineté** | Liste issue de l'API Géo (État, Licence Ouverte 2.0), source, licence et date dans le fichier et sur la page « Données personnelles » ou un pied de page de la recherche ; aucun service hors UE | ✅ |
| **IV. Méthode** | Aucun effet sur le score ni sur l'empreinte : le menu n'est pas écrit dans le rapport stocké | ✅ |
| **V. IA** | Aucune IA | ✅ |
| **VI. Terrain** | Rend les relevés (003) et le parcours (006) accessibles sans passer par un rapport | ✅ |
| **VII. Simplicité et tests** | Aucun service, aucune dépendance ; une seule implémentation de la recherche ; tests sans réseau sur la liste figée | ✅ |
| **VIII. Retour d'expérience** | Leçons appliquées : LL-011 (rapport d'une version antérieure), LL-012 (ordre des blocs insérés, essai navigateur), LL-017 (rendu vérifié dans un navigateur), LL-027 (arrondissements de Paris, `75056` exclu), LL-030 (sans session ⇒ connexion puis retour) | ✅ |
| **IX. Agents IA** | Branche dédiée, PR, fusion humaine | ✅ |
| Données personnelles | Frappes non journalisées, jamais transmises à un tiers ; aucune nouvelle donnée conservée | ✅ |

**Re-check après la conception (phase 1)** : conforme, aucune exception.

## Project Structure

### Documentation (this feature)

```text
specs/008-navigation-communes/
├── plan.md              # ce fichier
├── research.md          # phase 0 : R1 à R8
├── data-model.md        # phase 1 : liste de référence, menu, fil
├── quickstart.md        # phase 1 : tests, essai navigateur
├── contracts/
│   ├── http-api.md      # routes nouvelles et modifiées
│   └── interface.md     # menu, fil d'Ariane par page
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/territoire/liste_communes.py   # génère communes_idf.json (lancé à la main, R1)

src/bitumap/
├── territoire/
│   ├── communes_idf.json      # liste de référence versionnée
│   └── recherche.py           # chargement, normalisation, classement (R2, R3)
├── api/
│   ├── navigation.py          # entrées de menu, fil d'Ariane, globales des gabarits
│   ├── demandes.py            # /communes?q=|insee=, /communes/recherche, menu du rapport
│   ├── terrain.py             # GET /terrain (choix de commune)
│   ├── parcours.py            # GET /parcours (choix de commune)
│   ├── application.py         # session passée à la page d'erreur (R5)
│   ├── statique/communes.js   # propositions pendant la frappe
│   ├── statique/style.css     # menu, details, fil d'Ariane
│   └── gabarits/
│       ├── base.html          # menu + fil
│       ├── _menu.html, _fil.html, _recherche_commune.html
│       ├── choix_commune.html # /terrain et /parcours
│       ├── rapport_menu.html  # fragment inséré dans le rapport (R6)
│       └── … (rubrique et fil déclarés dans chaque page)

tests/
├── unit/test_communes_idf.py           # invariants, normalisation, SC-001
├── api/test_recherche_communes.py      # /communes?q=, JSON, code postal, API Géo en panne
├── api/test_navigation.py              # menu par profil, aria-current, fil par page
└── api/test_rapport_menu.py            # insertion, ancienne version, CSP, ordre des blocs
```

**Structure Decision**: la recherche rejoint `territoire/` (à côté de `api_geo.py`) ; la
navigation est déclarée une fois en Python et rendue par des gabarits partiels inclus
dans `base.html` et dans le fragment du rapport, pour un seul jeu d'entrées.

## Complexity Tracking

Aucune exception à la constitution.

## Dépendances et ordre

- Part de `main` ; **à rebaser après la fusion de la PR interface**
  (`fix/interface-heure-session`), qui modifie les mêmes gabarits (heure, session expirée,
  page d'erreur) : conflits attendus et simples.
- Ordre proposé : liste et recherche (US1) → menu (US2, pages puis rapport) → fil (US3).
- Mise en service : nouvelle version et digests (LL-023) ; aucune action OpenTofu.
