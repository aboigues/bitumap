"""Direction des quais (FR-030, T093) : terminus desservis depuis chaque quai.

Données : relations de lignes de bus OpenStreetMap (extrait Geofabrik du 2026-09-27) des
trois quais « Paix - Verdun » à Courbevoie, identifiés par leur référence IDFM.
"""

import json

import geopandas as gpd
from shapely.geometry import Point as PointGeo

from bitumap.modele import Point
from bitumap.points import direction
from bitumap.sources import osm

TERMINUS = {
    "23742": {
        "163": ["Nanterre - Préfecture RER"],
        "164": ["Argenteuil - Collège Claude Monet"],
        "175": ["Les Bruyères"],
        "278": ["Les Bruyères"],
    },
    "36806": {"163": ["Porte de Clichy"], "164": ["L'Yser et la Somme"]},
    "36807": {"175": ["Porte de Saint-Cloud"], "275": ["La Défense"], "278": ["La Défense"]},
}
LIGNES_IDFM = {
    "23742": ["163", "164", "175", "275", "278"],
    "36806": ["163", "164"],
    "36807": ["175", "275", "278"],
}


def _quais() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        [
            {"node_id": i, "ref_idfm": ref, "terminus": json.dumps(t)}
            for i, (ref, t) in enumerate(TERMINUS.items())
        ],
        geometry=[PointGeo(2.26, 48.90)] * len(TERMINUS),
        crs="EPSG:4326",
    )


def _arret(ref: str) -> Point:
    return Point(
        f"A{ref}",
        "arret",
        "Paix - Verdun",
        2.26,
        48.90,
        "Boulevard de Verdun",
        100,
        10,
        LIGNES_IDFM[ref],
    )


def test_trois_quais_paix_verdun_distincts():
    points = [_arret(ref) for ref in TERMINUS]
    direction.appliquer(points, _quais())
    assert points[0].direction == (
        "Argenteuil - Collège Claude Monet, Les Bruyères, Nanterre - Préfecture RER"
    )
    assert points[1].direction == "L'Yser et la Somme, Porte de Clichy"
    assert points[2].direction == "La Défense, Porte de Saint-Cloud"
    designations = {direction.designation(p) for p in points}
    assert len(designations) == 3


def test_designation_nom_direction_voie_lignes():
    point = _arret("36806")
    direction.appliquer([point], _quais())
    assert direction.designation(point) == (
        "Paix - Verdun · vers L'Yser et la Somme, Porte de Clichy · Boulevard de Verdun · 163, 164"
    )


def test_direction_inconnue_jamais_devinee():
    point = _arret("36806")
    point.id = "A99999"  # aucun quai OSM portant cette référence
    direction.appliquer([point], _quais())
    assert point.direction is None
    assert "direction non déterminée" in direction.designation(point)


def test_seules_les_lignes_du_quai_selon_idfm_comptent():
    point = _arret("36806")
    point.lignes = ["164"]
    direction.appliquer([point], _quais())
    assert point.direction == "L'Yser et la Somme"


def test_carrefours_sans_direction():
    feu = Point("F1", "feu", "Rue A × Rue B", 2.26, 48.90)
    direction.appliquer([feu], _quais())
    assert feu.direction is None
    assert "direction" not in direction.designation(feu)


def test_plusieurs_noeuds_pour_un_meme_quai():
    quais = _quais()
    doublon = quais.iloc[[1]].copy()
    doublon["terminus"] = json.dumps({"164": ["L'Yser et la Somme"], "163": ["Porte de Clichy"]})
    point = _arret("36806")
    direction.appliquer(
        [point],
        gpd.GeoDataFrame([*quais.to_dict("records"), *doublon.to_dict("records")], crs="EPSG:4326"),
    )
    assert point.direction == "L'Yser et la Somme, Porte de Clichy"


def test_terminus_d_un_itineraire_osm():
    assert osm.terminus({"to": "La  Défense "}) == "La Défense"
    assert osm.terminus({"name": "Bus 275 : Pont de Levallois → La Défense"}) == "La Défense"
    assert osm.terminus({"name": "Bus 275"}) is None


def test_paix_verdun_sur_les_fixtures_de_courbevoie():
    from pathlib import Path

    from bitumap.calcul import calculer_commune
    from bitumap.sources.fournisseur import FournisseurFige

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"
    resultat = calculer_commune(FournisseurFige(fixtures, "92026"), "Courbevoie")
    quais = {p.id: p for p in resultat.points if p.nom == "Paix - Verdun"}
    assert set(quais) == {"A23742", "A36806", "A36807"}
    assert len({direction.designation(p) for p in quais.values()}) == 3
    assert quais["A36807"].direction == "La Défense, Porte de Saint-Cloud"
    arrets = [p for p in resultat.points if p.type == "arret"]
    assert sum(1 for p in arrets if p.direction) / len(arrets) >= 0.9  # 92 % au 2026-09-27
