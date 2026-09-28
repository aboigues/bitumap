"""Sollicitation : type de point, arrêt proche d'un feu, pointe (méthode 1.0)."""

from __future__ import annotations

from bitumap.modele import Facteur, Point

EFFET_TYPE = {"arret": 1.0, "feu": 0.8, "giratoire": 0.7}
DISTANCE_FEU_M = 40
SEUIL_POINTE = 20


def calculer(point: Point, distance_feu_m: float | None) -> list[Facteur]:
    facteurs = [
        Facteur(
            "type",
            point.libelle_type,
            EFFET_TYPE[point.type],
            explication="Freinage, arrêt et redémarrage"
            if point.type == "arret"
            else point.libelle_type,
            visible=False,
        )
    ]
    if point.type == "arret" and distance_feu_m is not None and distance_feu_m < DISTANCE_FEU_M:
        facteurs.append(
            Facteur(
                "arret_pres_feu",
                round(distance_feu_m),
                1.2,
                explication="Arrêt à moins de 40 m d'un feu",
                unite="m",
            )
        )
    if point.pointe_h is not None and point.pointe_h >= SEUIL_POINTE:
        facteurs.append(
            Facteur(
                "pointe",
                round(point.pointe_h),
                1.1,
                explication=f"{point.pointe_h:.0f} bus/h en pointe",
                unite="bus/h",
            )
        )
    return facteurs
