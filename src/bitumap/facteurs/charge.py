"""Charge : passages de bus par jour, en échelle logarithmique (méthode 1.0)."""

from __future__ import annotations

import math

from bitumap.modele import Facteur, Point


def calculer(point: Point) -> Facteur:
    effet = math.log(max(point.bus_jour, 1.0) + 1.0)
    return Facteur(
        "charge",
        round(point.bus_jour, 1),
        effet,
        explication=f"{point.bus_jour:.0f} passages de bus par jour",
        unite="bus/jour",
        visible=False,
    )
