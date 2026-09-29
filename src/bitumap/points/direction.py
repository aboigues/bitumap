"""Direction des quais (FR-030) : terminus desservis depuis chaque quai d'arrêt.

Source : relations de lignes de bus OpenStreetMap (research R11). Un quai IDFM (``A{id}``)
est relié aux nœuds OSM qui portent sa référence (``ref:FR:STIF``) ; sa direction est la
liste des terminus des itinéraires qui le desservent, limitée aux lignes qu'IDFM y fait
passer. Aucun terminus ⇒ ``None``, affiché « direction non déterminée » : jamais deviné.
Descriptive : sans effet sur le score ni le classement.
"""

from __future__ import annotations

import json

import geopandas as gpd

from bitumap.modele import Point

NON_DETERMINEE = "direction non déterminée"


def terminus_par_quai(quais: gpd.GeoDataFrame) -> dict[str, dict[str, set[str]]]:
    """{référence IDFM: {ligne: {terminus}}}, en fusionnant les nœuds d'un même quai."""
    resultat: dict[str, dict[str, set[str]]] = {}
    for ligne in quais.itertuples():
        for ref in str(ligne.ref_idfm).split(";"):
            par_ligne = resultat.setdefault(ref.strip(), {})
            for nom_ligne, terminus in json.loads(ligne.terminus).items():
                par_ligne.setdefault(nom_ligne, set()).update(terminus)
    return resultat


def appliquer(points: list[Point], quais: gpd.GeoDataFrame) -> None:
    connus = terminus_par_quai(quais)
    for p in points:
        if p.type != "arret":
            continue
        par_ligne = connus.get(p.id.removeprefix("A"), {})
        terminus = {t for ligne in p.lignes for t in par_ligne.get(ligne, ())}
        p.direction = ", ".join(sorted(terminus)) if terminus else None


def designation(p: Point) -> str:
    """« nom · direction · voie · lignes » (FR-030) ; la direction ne concerne que les arrêts."""
    parties = [p.nom]
    if p.type == "arret":
        parties.append(f"vers {p.direction}" if p.direction else NON_DETERMINEE)
    parties.append(p.voie or "voie inconnue")
    if p.lignes:
        parties.append(", ".join(p.lignes))
    return " · ".join(parties)


def identifiant(p: Point) -> str:
    """Identifiant affiché : identifiant IDFM du quai pour un arrêt (FR-030)."""
    return f"quai IDFM {p.id.removeprefix('A')}" if p.type == "arret" else f"point {p.id}"
