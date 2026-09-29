# Specification Quality Checklist: Parcours de surveillance

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-29
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Itération 1 (2026-09-29) : deux marqueurs, tranchés par le mainteneur le même jour :
  FR-005 → visite dans l'ordre du rang, les plus critiques d'abord (option B) ; FR-006 →
  durée maximale choisie par l'agent (option B), points pris dans l'ordre du rang tant que la
  boucle tient (trajets, arrêts de 5 min, retour), les autres listés « non visités ».
  SC-003 (tournée ≤ +20 % d'une tournée manuelle) remplacé : l'ordre du rang allonge
  volontairement le trajet ; ajout de SC-007 (durée estimée fiable à ±20 %).
- Itération 2 : tous les points passent.
- « GPX » est le format de sortie demandé par l'utilisateur (issue #21), pas un choix
  technique.
- Numéro 006 imposé par la feuille de route (005 réservé à l'échelle du département) :
  branche et dossier nommés explicitement.
