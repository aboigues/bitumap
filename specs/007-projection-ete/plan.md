# Implementation Plan: Projection de l'orniérage été par été

**Branch**: `007-projection-ete` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-projection-ete/spec.md`

## Summary

Pour chaque point du rapport d'une commune, un score projeté été après été (5 étés) selon
trois scénarios tirés d'étés observés à Paris-Montsouris : moyen (2016–2025), chaud (2022),
très chaud (2026, le plus sévère : 196 degrés-jours au-dessus de 30 °C, près du double de
2003). Le score part du score du rapport et croît avec la sévérité de l'été, la sensibilité
du point à la chaleur et la fréquentation. Seuil d'intervention : 95/100 (décision du
mainteneur) ; coefficient calé pour que « Paix - Verdun » l'atteigne dès le premier été très
chaud. Calcul à la demande par l'API, sans stockage ; page, fiches avec courbes SVG, export
CSV.

## Technical Context

**Language/Version**: Python 3.14 (paquet `bitumap`)

**Primary Dependencies**: celles de 002 (FastAPI, jinja2, httpx) ; SVG produit par gabarit ;
**aucune nouvelle dépendance**

**Storage**: aucune table ; sévérités des étés en cache (bucket de cache, partagé avec 004)

**Testing**: pytest ; étés figés en fixtures ; propriétés de monotonie et de reproductibilité
vérifiées sur tous les points de Courbevoie

**Target Platform**: API de 002 (Scaleway Serverless Containers)

**Project Type**: service web (extension de l'API de 002)

**Performance Goals**: page calculée en moins d'une seconde pour une commune de
1 500 points

**Constraints**: indice relatif, jamais en millimètres ; déterministe ; données ouvertes
hébergées dans l'UE

**Scale/Scope**: 5 étés × 3 scénarios × jusqu'à 1 500 points par commune

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| **I. Sécurité** | Lecture seule, session requise ; paramètre de fréquentation borné ; aucune donnée nouvelle exposée | ✅ |
| **II. Zéro coût au repos** | Calcul à la demande, sans stockage ni ressource nouvelle | ✅ |
| **III. Souveraineté** | Météo-France, Licence Ouverte, fichiers hébergés en France ; source citée dans la page et l'export ; Météo-France est une nouvelle source hors de la liste « V1 » du principe III (même amendement que 004) | ⚠️ amendement commun avec 004 |
| **IV. Méthode reproductible** | Formule publiée (R3), version de projection distincte, paramètres affichés ; déterministe ; ne modifie jamais le score du rapport | ✅ |
| **V. IA** | Âge de l'enrobé par IA seulement lu (« à confirmer ») | ✅ |
| **VI. Terrain** | Réfections relevées (003) prises en compte ; recalage prévu sur les relevés répétés | ✅ |
| **VII. Simplicité et tests** | Aucun service ni dépendance nouveaux ; propriétés testées sur Courbevoie | ✅ |
| **VIII. Retour d'expérience** | Calage sur le constat réel de « Paix - Verdun » ; limite (un seul point) documentée | ✅ |
| **IX. Agents IA** | Branche dédiée, PR, fusion humaine | ✅ |

**Re-check après la conception (phase 1)** : conforme, sous réserve de l'amendement du
principe III commun avec 004 (ajout des sources ouvertes de la v2).

## Project Structure

### Documentation (this feature)

```text
specs/007-projection-ete/
├── plan.md              # ce fichier
├── research.md          # phase 0 : R1 à R6 (étés mesurés, formule, calage)
├── data-model.md        # phase 1 : été, scénario, trajectoire
├── quickstart.md        # phase 1 : vérifications et parcours
├── contracts/
│   └── http-api.md      # phase 1 : page, fiche, export
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/bitumap/
├── sources/meteo.py        # relevés quotidiens Météo-France, sévérité des étés (partagé avec 004)
├── projection/
│   ├── scenarios.py        # moyen, chaud, très chaud ; rapport r
│   ├── calcul.py           # score projeté, été du seuil, réfections (003)
│   └── courbes.py          # SVG
├── api/
│   ├── projection.py       # routes /projection/…
│   └── gabarits/projection/ # page, fiche
├── score/methode.py        # VERSION_PROJECTION, k, seuils
└── rapport/gabarits/rapport.html.j2   # lien vers la projection

tests/projection/           # formule, monotonie, reproductibilité, calage A23742, export
```

**Structure Decision**: module `projection/` indépendant du calcul du score ; il ne lit que
le rapport produit et les étés, ce qui garantit qu'il ne modifie jamais le score.

## Complexity Tracking

Aucune exception à la constitution (l'amendement du principe III est commun avec 004).

## Dépendances et ordre

- **Autonome** : utilisable dès maintenant sur les rapports 1.2 ; bénéficiera de la méthode
  2.0 (004) sans changement.
- `sources/meteo.py` : développé une fois, partagé avec 004 (celui qui arrive en premier le
  crée).
- **Recalage** de `k` et du seuil : après les relevés répétés de 003.
