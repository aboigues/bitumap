"""Îlot de chaleur : aléa de jour de l'Institut Paris Region (0 à 16) → ×0,92 à ×1,08."""

from __future__ import annotations

from bitumap.modele import Facteur

SEUIL_MARQUE = 11


def effet_alea(alea: float) -> float:
    return 0.92 + 0.16 * max(0.0, min(16.0, alea)) / 16


def calculer(alea: float | None, lcz: str | None) -> Facteur:
    if alea is None or alea < 0:
        return Facteur(
            "chaleur", None, 1.0, statut="non_evalue", explication="Îlot de chaleur non évalué"
        )
    marque = alea >= SEUIL_MARQUE
    return Facteur(
        "chaleur",
        int(alea),
        effet_alea(alea),
        explication=f"Îlot de chaleur marqué (aléa jour {int(alea)}/16)"
        if marque
        else f"Aléa de chaleur de jour {int(alea)}/16"
        + (f", zone climatique {lcz}" if lcz else ""),
        unite="/16",
        visible=marque,
    )
