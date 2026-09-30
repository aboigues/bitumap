"""Ensoleillement de la méthode 2.0 sur hauteurs LiDAR (004 T014, R1, R2), grilles
synthétiques, sans réseau."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point, box

from bitumap.calcul import _zone_carrefour
from bitumap.facteurs import ensoleillement as e
from bitumap.sources.base import Hauteurs

X, Y = 650_000.0, 6_865_000.0  # Lambert 93, autour de Courbevoie
LON, LAT = 2.259, 48.902
SOL = 30.0
COTE = 2 * e.DEMI_COTE_M
SANS_BATIMENT = gpd.GeoDataFrame({"hauteur": []}, geometry=[], crs="EPSG:2154")


def _grilles():
    return np.full((COTE, COTE), SOL, dtype=np.float32), np.full(
        (COTE, COTE), SOL, dtype=np.float32
    )


def _hauteurs(mns, mnt, millesime="22LHDKE 2023-03-03"):
    return Hauteurs(mns, mnt, (X - e.DEMI_COTE_M, Y + e.DEMI_COTE_M), 1.0, millesime)


def _cellules(xmin, ymin, xmax, ymax):
    """Tranche (lignes, colonnes) de la grille couvrant le rectangle Lambert 93 donné."""
    x0, y0 = X - e.DEMI_COTE_M, Y + e.DEMI_COTE_M
    return slice(int(y0 - ymax), int(y0 - ymin)), slice(int(xmin - x0), int(xmax - x0))


def _calculer(
    mns, mnt, batiments=SANS_BATIMENT, vegetation=None, tabliers=None, echantillons=None, **kw
):
    return e.calculer_v2(
        LON,
        LAT,
        echantillons or [(X, Y)],
        _hauteurs(mns, mnt),
        batiments,
        tabliers,
        vegetation,
        **kw,
    )


def test_periode_chaude_six_jours_heure_par_heure():
    azimuts, elevations = e.positions_soleil_ete(LAT, LON)
    assert len(azimuts) == len(elevations) == len(e.JOURS_ETE) * len(e.HEURES_ETE) == 72
    assert [j[5:] for j in e.JOURS_ETE] == ["06-01", "06-15", "07-01", "07-15", "08-01", "08-15"]


def test_place_degagee_plein_soleil():
    mns, mnt = _grilles()
    f = _calculer(mns, mnt)
    assert f.valeur == 12.0 and f.effet == pytest.approx(1.2)
    assert f.details["source"] == "lidar_hd" and f.details["cause_ombre"] is None
    assert f.details["millesime_lidar"] == "22LHDKE 2023-03-03"


def test_orientation_de_la_rue():
    # Rue canyon de 16 m entre des façades de 20 m : est-ouest contre nord-sud.
    mns, mnt = _grilles()
    ew = mns.copy()
    ew[_cellules(X - 100, Y + 8, X + 100, Y + 30)] = SOL + 20
    ew[_cellules(X - 100, Y - 30, X + 100, Y - 8)] = SOL + 20
    ns = mns.copy()
    ns[_cellules(X + 8, Y - 100, X + 30, Y + 100)] = SOL + 20
    ns[_cellules(X - 30, Y - 100, X - 8, Y + 100)] = SOL + 20
    h_ew, h_ns = _calculer(ew, mnt).valeur, _calculer(ns, mnt).valeur
    assert abs(h_ew - h_ns) >= 1.0


def test_arbre_mesure_plutot_que_forfaitaire():
    # Arbre de 15 m mesuré à 10 m au sud : plus d'ombre que l'arbre forfaitaire de 8 m (1.2).
    mns, mnt = _grilles()
    zone = _cellules(X - 15, Y - 18, X + 15, Y - 6)
    mns[zone] = SOL + 15
    vegetation = np.zeros((COTE, COTE), dtype=bool)
    vegetation[zone] = True
    v2 = _calculer(mns, mnt, vegetation=vegetation)
    v12 = e.calculer(LON, LAT, [(X, Y, vegetation)], SANS_BATIMENT)
    assert v2.valeur < v12.valeur
    assert v2.details["cause_ombre"] == "arbre"


def test_trou_du_houppier_hivernal_comble():
    # LiDAR d'hiver : houppier troué ; les cellules de végétation prennent la hauteur voisine.
    mns, mnt = _grilles()
    zone = _cellules(X - 15, Y - 18, X + 15, Y - 6)
    mns[zone] = SOL + 15
    vegetation = np.zeros((COTE, COTE), dtype=bool)
    vegetation[zone] = True
    troue = mns.copy()
    troue[zone] = np.where(np.indices(troue[zone].shape).sum(axis=0) % 2 == 0, SOL + 15, SOL)
    assert (
        _calculer(troue, mnt, vegetation=vegetation).valeur
        == _calculer(mns, mnt, vegetation=vegetation).valeur
    )


def test_relief():
    # Coteau raide au sud : le terrain monte de 3 m par mètre à partir de 5 m du point ; il
    # cache le soleil de midi (au sud, jusqu'à 64° de hauteur l'été), pas celui du matin.
    _, mnt = _grilles()
    lignes = np.arange(COTE)
    y_cellule = (Y + e.DEMI_COTE_M) - lignes - 0.5
    montee = (3 * np.clip((Y - 5) - y_cellule, 0, None)).astype(np.float32)
    mnt = mnt + montee[:, None]
    f = _calculer(mnt.copy(), mnt)
    assert f.valeur <= 9.0 and f.details["cause_ombre"] == "relief"


def test_cause_batiment():
    mns, mnt = _grilles()
    rect = (X - 20, Y - 25, X + 20, Y - 6)
    mns[_cellules(*rect)] = SOL + 25
    batiments = gpd.GeoDataFrame({"hauteur": [25.0]}, geometry=[box(*rect)], crs="EPSG:2154")
    f = _calculer(mns, mnt, batiments=batiments)
    assert f.valeur < 12.0 and f.details["cause_ombre"] == "batiment"


def test_hauteurs_absentes_repli_1_2():
    f = e.calculer_v2(LON, LAT, [(X, Y)], None, SANS_BATIMENT, None, None)
    assert f.details["source"] == "repli_1.2"
    assert f.explication.startswith("Ensoleillement estimé (données de hauteur incomplètes)")
    assert f.valeur == e.calculer(LON, LAT, [(X, Y, None)], SANS_BATIMENT).valeur


def test_sol_inconnu_au_point_repli_1_2():
    mns, mnt = _grilles()
    mnt[e.DEMI_COTE_M, e.DEMI_COTE_M] = np.nan
    assert _calculer(mns, mnt).details["source"] == "repli_1.2"


def test_zone_de_mesure_d_un_carrefour():
    centre = Point(X, Y)
    une = [LineString([(X - 50, Y), (X + 50, Y)])]
    pts = _zone_carrefour(une, centre)
    assert len(pts) == 5 and (X, Y) in pts
    assert all(abs(py - Y) < 1e-6 and abs(px - X) <= 10 for px, py in pts)
    deux = [*une, LineString([(X, Y - 50), (X, Y + 50)])]
    pts = _zone_carrefour(deux, centre)
    assert len(pts) == 5
    assert sum(abs(px - X) < 1e-6 and py != Y for px, py in pts) == 2  # deux sur la seconde voie


def test_source_affichee_dans_l_explication():
    mns, mnt = _grilles()
    assert _calculer(mns, mnt).explication.endswith("(LiDAR HD de mars 2023)")
    assert e.libelle_millesime("inattendu") == "LiDAR HD"


def test_vehicule_du_survol_ignore():
    # Véhicule de 3 m garé à 3 m du point lors du survol : pas un obstacle durable.
    mns, mnt = _grilles()
    mns[_cellules(X - 6, Y - 5, X + 6, Y - 3)] = SOL + 3
    assert _calculer(mns, mnt).valeur == 12.0


def test_cause_arbre_malgre_un_leger_decalage_de_l_infrarouge():
    mns, mnt = _grilles()
    zone = _cellules(X - 15, Y - 18, X + 15, Y - 6)
    mns[zone] = SOL + 15
    vegetation = np.zeros((COTE, COTE), dtype=bool)
    decale = _cellules(X - 14, Y - 17, X + 14, Y - 7)  # masque un peu plus petit que l'arbre
    vegetation[decale] = True
    assert _calculer(mns, mnt, vegetation=vegetation).details["cause_ombre"] == "arbre"


def test_mat_de_feu_ignore():
    # Mât de feu de 8 m capté par le LiDAR à 2 m du point : objet fin, pas une ombre de rue.
    mns, mnt = _grilles()
    mns[_cellules(X, Y - 3, X + 1, Y - 2)] = SOL + 8
    assert _calculer(mns, mnt).valeur == 12.0


def test_houppier_rugueux_classe_arbre_sans_infrarouge():
    # Arbres à l'ombre d'immeubles : l'infrarouge ne les voit pas, leur relief irrégulier si
    # (houppiers de 3 m de large de hauteurs différentes ; les objets plus fins sont effacés).
    mns, mnt = _grilles()
    lignes, colonnes = _cellules(X - 15, Y - 18, X + 15, Y - 6)
    indices = np.indices((lignes.stop - lignes.start, colonnes.stop - colonnes.start)) // 3
    bosses = 12 + 4 * (indices.sum(axis=0) % 3)
    mns[lignes, colonnes] = SOL + bosses
    assert _calculer(mns, mnt).details["cause_ombre"] == "arbre"


def test_construction_lisse_non_repertoriee_classe_batiment():
    mns, mnt = _grilles()
    mns[_cellules(X - 15, Y - 18, X + 15, Y - 6)] = SOL + 14  # toit plat hors BD TOPO
    assert _calculer(mns, mnt).details["cause_ombre"] == "batiment"
