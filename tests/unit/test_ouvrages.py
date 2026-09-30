"""Ponts et passerelles dans l'ensoleillement (méthode 1.2, issue #18).

Cas d'origine : « Verdun - Rue Latérale » (A27418) à Courbevoie, sous le pont de la ligne
Paris-Saint-Lazare – Versailles-Rive-Droite : la chaussée y est à l'ombre.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from bitumap.calcul import _tabliers_au_dessus
from bitumap.facteurs import ensoleillement
from bitumap.sources import osm

X, Y = 650_000.0, 6_865_000.0  # Lambert 93, autour de Courbevoie
LON, LAT = 2.259, 48.902
SANS_BATIMENT = gpd.GeoDataFrame({"hauteur": []}, geometry=[], crs="EPSG:2154")


def _ouvrages(*lignes):
    return gpd.GeoDataFrame(
        [
            {"way_id": i, "genre": genre, "niveau": niveau, "largeur_m": largeur}
            for i, (genre, niveau, largeur, _) in enumerate(lignes, start=1)
        ],
        geometry=[geom for *_, geom in lignes],
        crs="EPSG:2154",
    )


def _pont_ferroviaire_au_dessus():
    # Voie ferrée est-ouest passant au-dessus du point, 2 voies de 5 m (défaut)
    return _ouvrages(
        ("rail", 1, None, LineString([(X - 80, Y + 2), (X + 80, Y + 2)])),
        ("rail", 1, None, LineString([(X - 80, Y - 3), (X + 80, Y - 3)])),
    )


def test_genre_des_ouvrages_osm():
    assert osm.genre_ouvrage({"bridge": "yes", "railway": "rail"}) == "rail"
    assert osm.genre_ouvrage({"bridge": "viaduct", "highway": "primary"}) == "route"
    assert osm.genre_ouvrage({"bridge": "yes", "highway": "footway"}) == "pieton"
    assert osm.genre_ouvrage({"bridge": "no", "highway": "primary"}) is None
    assert osm.genre_ouvrage({"highway": "primary"}) is None
    assert osm.genre_ouvrage({"bridge": "yes", "waterway": "canal"}) is None


def test_chaussee_sous_un_pont_ferroviaire_a_l_ombre():
    azimuts, elevations = ensoleillement.positions_soleil(LAT, LON)
    ouvert = ensoleillement.heures_de_soleil(
        ensoleillement.grille_hauteurs(X, Y, SANS_BATIMENT, None), azimuts, elevations
    )
    tabliers = ensoleillement.tabliers(_pont_ferroviaire_au_dessus())
    dessous = ensoleillement.heures_de_soleil(
        ensoleillement.grille_hauteurs(X, Y, SANS_BATIMENT, None, tabliers), azimuts, elevations
    )
    assert ouvert == 12.0
    assert dessous <= 1.0


def test_facteur_explique_l_ouvrage():
    tabliers = ensoleillement.tabliers(_pont_ferroviaire_au_dessus())
    f = ensoleillement.calculer(LON, LAT, [(X, Y, None)], SANS_BATIMENT, tabliers)
    assert f.explication.startswith("Chaussée sous un pont ferroviaire")
    assert f.visible and f.effet < 0.85


def test_zone_d_arret_en_partie_sous_le_pont():
    """Poteau au bord du tablier, bus arrêté dessous (cas de A27418) : la moyenne sur la
    zone d'arrêt compte l'ombre du pont, la mesure au poteau seul ne la voyait pas."""
    tabliers = ensoleillement.tabliers(
        _ouvrages(("rail", 1, 14.0, LineString([(X - 80, Y - 8), (X + 80, Y - 8)])))
    )
    # zone d'arrêt nord-sud : poteau à 2 m du bord nord du tablier, bus au sud (dessous)
    zone = [(X, Y + 1 - d, None) for d in (0, 3, 6, 9, 12)]
    au_poteau = ensoleillement.calculer(LON, LAT, zone[:1], SANS_BATIMENT, tabliers)
    sur_la_zone = ensoleillement.calculer(LON, LAT, zone, SANS_BATIMENT, tabliers)
    assert sur_la_zone.valeur <= 1.5 and sur_la_zone.valeur <= au_poteau.valeur - 3
    assert sur_la_zone.explication.startswith("Zone d'arrêt en partie sous un pont ferroviaire")


def test_zone_de_mesure_selon_le_sens_de_circulation():
    from bitumap.calcul import _zone_de_mesure
    from bitumap.modele import Point as PointRapport

    voie = pd.Series(
        {"geometry": LineString([(X - 100, Y), (X + 100, Y)]), "sens_unique": True}
    )  # circulation vers l'est
    arret = PointRapport("A1", "arret", "Arrêt", LON, LAT)
    zone = _zone_de_mesure(arret, voie, Point(X, Y))
    assert [round(x - X) for x, _ in zone] == [0, -3, -6, -9, -12]  # en amont, à l'ouest
    voie["sens_unique"] = False
    assert [round(x - X) for x, _ in _zone_de_mesure(arret, voie, Point(X, Y))] == [
        -6,
        -3,
        0,
        3,
        6,
    ]
    feu = PointRapport("F1", "feu", "Carrefour", LON, LAT)
    assert _zone_de_mesure(feu, voie, Point(X, Y)) == [(X, Y)]


def test_passerelle_accord():
    tabliers = ensoleillement.tabliers(
        _ouvrages(("pieton", 1, 4.0, LineString([(X, Y - 50), (X, Y + 50)])))
    )
    assert ensoleillement.sous_ouvrage(X, Y, tabliers) == "une passerelle"


def test_hauteur_selon_le_niveau_et_largeur_osm():
    tabliers = ensoleillement.tabliers(
        _ouvrages(("route", 2, 12.0, LineString([(X - 10, Y), (X + 10, Y)])))
    )
    assert tabliers.hauteur.iloc[0] == 2 * ensoleillement.HAUTEUR_TABLIER_M
    assert abs(tabliers.geometry.iloc[0].area - 20 * 12) < 1


def test_bus_sur_le_pont_non_ombre_par_son_propre_tablier():
    pont = LineString([(X - 50, Y), (X + 50, Y)])
    tabliers = ensoleillement.tabliers(_ouvrages(("route", 1, None, pont)))
    chaussee = Point(X, Y)
    # le bus roule sur un autre tronçon OSM du même pont (way_id différent)
    voie = pd.Series({"way_id": 999, "pont": True})
    assert _tabliers_au_dessus(tabliers, voie, chaussee).empty
    # la voie du bus elle-même n'est jamais un obstacle
    voie = pd.Series({"way_id": 1, "pont": False})
    assert _tabliers_au_dessus(tabliers, voie, chaussee).empty
    # une route qui passe sous ce pont, elle, est ombrée
    voie = pd.Series({"way_id": 999, "pont": False})
    assert len(_tabliers_au_dessus(tabliers, voie, chaussee)) == 1


def test_grilles_de_zone_identiques_aux_grilles_individuelles():
    """Optimisation : les grilles découpées dans une grille élargie sont celles qu'on aurait
    calculées point par point (décalages entiers)."""
    batiments = gpd.GeoDataFrame(
        {"hauteur": [20.0, None]},
        geometry=[Point(X + 15, Y + 5).buffer(8), Point(X - 30, Y - 20).buffer(5)],
        crs="EPSG:2154",
    )
    tabliers = ensoleillement.tabliers(_pont_ferroviaire_au_dessus())
    zone = [(X, Y - d, None) for d in (0, 3, 6, 9, 12)]
    for (x, y, _), grille in zip(
        zone, ensoleillement.grilles_zone(zone, batiments, tabliers), strict=True
    ):
        attendue = ensoleillement.grille_hauteurs(x, y, batiments, None, tabliers)
        assert (grille == attendue).all()


# --- Méthode 2.0 : tablier mesuré par le LiDAR (004 T015) -----------------------------------

import numpy as np  # noqa: E402

from bitumap.sources.base import Hauteurs  # noqa: E402

SOL = 30.0
COTE = 2 * ensoleillement.DEMI_COTE_M


def _lidar_pont(largeur_nord=2, largeur_sud=8, epaisseur_tablier=1.5):
    """Tablier est-ouest à 6 m au-dessus de la chaussée, de Y − largeur_sud à Y + largeur_nord."""
    mns = np.full((COTE, COTE), SOL, dtype=np.float32)
    mnt = mns.copy()
    y0 = Y + ensoleillement.DEMI_COTE_M
    mns[int(y0 - (Y + largeur_nord)) : int(y0 - (Y - largeur_sud)), :] = SOL + 6 + epaisseur_tablier
    return Hauteurs(mns, mnt, (X - ensoleillement.DEMI_COTE_M, y0), 1.0, "22LHDKE 2023-03-03")


def test_v2_chaussee_sous_un_tablier_mesure():
    tabliers = ensoleillement.tabliers(_pont_ferroviaire_au_dessus())
    f = ensoleillement.calculer_v2(LON, LAT, [(X, Y)], _lidar_pont(), SANS_BATIMENT, tabliers, None)
    assert f.valeur <= 1.0
    assert f.details["cause_ombre"] == "ouvrage" and "sous un pont ferroviaire" in f.explication


def test_v2_bus_sur_le_pont_sans_ombre_du_tablier():
    h = _lidar_pont()
    f = ensoleillement.calculer_v2(
        LON, LAT, [(X, Y)], h, SANS_BATIMENT, None, None, sur_un_pont=True
    )
    assert f.valeur == 12.0


def test_v2_zone_d_arret_au_bord_du_tablier():
    # Poteau au bord du tablier (issue #18) : le bus s'arrête en partie dessous.
    tabliers = ensoleillement.tabliers(_pont_ferroviaire_au_dessus())
    zone = [(X - 12 + 3 * i, Y) for i in range(5)]
    h = _lidar_pont()
    h.mns[:, int(X - 2 - (X - ensoleillement.DEMI_COTE_M)) :] = SOL  # tablier jusqu'à X − 2
    f = ensoleillement.calculer_v2(LON, LAT, zone, h, SANS_BATIMENT, tabliers, None)
    assert f.valeur < 12.0 and f.details["cause_ombre"] == "ouvrage"
