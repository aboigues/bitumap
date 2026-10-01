"""Poids lourds hors bus, méthode 2.0 (004 US3, FR-009, FR-010, R5).

Le point reçoit le comptage publié de **sa voie** : section à moins de
``RAYON_RATTACHEMENT_M`` de la chaussée, de même numéro de route ou dont l'adresse du
compteur porte le nom de la voie. Les poids lourds comptés comprennent les bus, déjà pris
en compte par la charge : les bus du sens (IDFM) sont retirés (décision du mainteneur,
2026-10-01). Effet borné, croissant avec le logarithme des poids lourds du sens le plus
chargé (bornes dans ``score.methode``). Sans comptage : effet neutre, « non évalué », quel
que soit le type de route.
"""

from __future__ import annotations

import math

import geopandas as gpd

from bitumap.facteurs.voirie import normaliser_nom
from bitumap.modele import Facteur
from bitumap.score.methode import EFFET_PL_MAX, PL_EFFET_MAX, PL_EFFET_NUL

NOM = "poids_lourds"
RAYON_RATTACHEMENT_M = 30


def rattacher(comptages_l93: gpd.GeoDataFrame | None, chaussee, numero: str | None, nom_voie):
    """Section comptée de la voie du point, ou ``None`` : la plus proche, puis la plus
    récente, puis la première par libellé (déterminisme)."""
    if comptages_l93 is None or comptages_l93.empty:
        return None
    distances = comptages_l93.distance(chaussee)
    proches = comptages_l93[distances <= RAYON_RATTACHEMENT_M]
    if proches.empty:
        return None
    nom = normaliser_nom(nom_voie)
    numero = numero or ""

    def meme_voie(section) -> bool:
        if numero and numero in str(section.numeros).split(";"):
            return True
        return bool(nom) and nom in normaliser_nom(section.libelle)

    memes = proches[[meme_voie(s) for s in proches.itertuples()]]
    if memes.empty:
        return None
    memes = memes.assign(_d=distances[memes.index].round(3))
    return memes.sort_values(["_d", "annee", "troncon"], ascending=[True, False, True]).iloc[0]


def effet(pl_jour: float) -> float:
    """×1,0 jusqu'à ``PL_EFFET_NUL`` poids lourds par jour, ×``EFFET_PL_MAX`` à partir de
    ``PL_EFFET_MAX``, linéaire en logarithme entre les deux."""
    if pl_jour <= PL_EFFET_NUL:
        return 1.0
    t = math.log(pl_jour / PL_EFFET_NUL) / math.log(PL_EFFET_MAX / PL_EFFET_NUL)
    return 1.0 + (EFFET_PL_MAX - 1.0) * min(1.0, t)


def calculer(section, bus_sens: float) -> Facteur:
    if section is None:
        return Facteur(
            NOM,
            None,
            1.0,
            statut="non_evalue",
            explication="Poids lourds : non évalué (aucun comptage publié)",
            unite="PL/jour",
            visible=False,
        )
    comptes = float(section.pl_sens)
    hors_bus = max(0.0, comptes - bus_sens)
    e = effet(hors_bus)
    return Facteur(
        NOM,
        round(hors_bus),
        e,
        explication=(
            f"{hors_bus:.0f} poids lourds par jour hors bus, sens le plus chargé "
            f"({section.source}, {section.troncon}, comptage {int(section.annee)})"
        ),
        unite="PL/jour",
        visible=e > 1.0,
        details={
            "source": str(section.source),
            "annee": int(section.annee),
            "troncon": str(section.troncon),
            "pl_comptes": round(comptes),
            "bus_retires": round(bus_sens),
        },
    )
