"""Combinaison des facteurs, rangs et priorités (méthode 1.0 ; FR-011, FR-012, FR-014).

1. score brut = produit des effets de tous les facteurs sauf l'âge de l'enrobé ;
2. priorités par rang, **figées** : P1 = 20 % premiers, P2 = 40 % suivants, P3 = reste ;
3. âge de l'enrobé (IA, P1 uniquement) : modifie le score et le rang **à l'intérieur des P1**,
   jamais la priorité (principe V, SC-012) ;
4. score affiché 0–100 relatif au maximum de la commune.

Tri déterministe : score décroissant, puis identifiant.
"""

from __future__ import annotations

import math

from bitumap.modele import Point
from bitumap.score.methode import PART_P1, PART_P2

FACTEUR_IA = "age_enrobe"


def _produit(point: Point, exclure: set[str]) -> float:
    return math.prod(f.effet for f in point.facteurs if f.nom not in exclure)


def _ordonner(points: list[Point]) -> list[Point]:
    return sorted(points, key=lambda p: (-round(p.score_brut, 9), p.id))


def prioriser(points: list[Point]) -> list[Point]:
    """Rangs et priorités hors IA ; renvoie les points triés."""
    for p in points:
        p.score_brut = _produit(p, {FACTEUR_IA})
    tries = _ordonner(points)
    n = len(tries)
    # Epsilon : 0,2 + 0,4 vaut 0,6000000000000001 en virgule flottante.
    n_p1 = math.ceil(n * PART_P1 - 1e-9)
    n_p2 = math.ceil(n * (PART_P1 + PART_P2) - 1e-9) - n_p1
    for i, p in enumerate(tries):
        p.priorite = "P1" if i < n_p1 else ("P2" if i < n_p1 + n_p2 else "P3")
    return tries


def finaliser(points: list[Point]) -> list[Point]:
    """Applique l'âge de l'enrobé à l'intérieur de chaque priorité, puis rangs et scores."""
    groupes = {"P1": [], "P2": [], "P3": []}
    for p in points:
        p.score_brut = _produit(p, set())
        groupes[p.priorite].append(p)
    ordonnes = [p for prio in ("P1", "P2", "P3") for p in _ordonner(groupes[prio])]
    maximum = max((p.score_brut for p in ordonnes), default=1.0) or 1.0
    for rang, p in enumerate(ordonnes, start=1):
        p.rang = rang
        p.score = round(100 * p.score_brut / maximum)
    return ordonnes
