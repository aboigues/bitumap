"""Facteur poids lourds hors bus, méthode 2.0 (004 T031, FR-009, FR-010, R5)."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from bitumap.facteurs import poids_lourds
from bitumap.score.methode import EFFET_PL_MAX, PL_EFFET_MAX, PL_EFFET_NUL
from bitumap.sources import comptages


def _comptages(*sections) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        [
            {
                "source": comptages.SOURCE_92,
                "troncon": f"{numeros}, {libelle}",
                "numeros": numeros,
                "libelle": libelle,
                "pl_sens": pl,
                "annee": annee,
            }
            for numeros, libelle, pl, annee, _ in sections
        ],
        geometry=[LineString([(0, y), (500, y)]) for *_, y in sections],
        crs="EPSG:2154",
    )


CHAUSSEE = Point(250, 0)


def test_rattache_a_la_meme_voie_par_numero():
    g = _comptages(("D908", "33 boulevard de Verdun", 474.0, 2021, 20))
    s = poids_lourds.rattacher(g, CHAUSSEE, "D908", "Boulevard de Verdun")
    assert s is not None and s.troncon == "D908, 33 boulevard de Verdun"


def test_rattache_par_le_nom_de_la_voie():
    g = _comptages(("D106", "43 rue de Colombes", 249.0, 2021, 5))
    assert poids_lourds.rattacher(g, CHAUSSEE, None, "Rue de Colombes") is not None


def test_autre_voie_a_10_m_non_rattachee():
    g = _comptages(("D7", "23 quai du Président Paul Doumer", 1825.0, 2021, 10))
    assert poids_lourds.rattacher(g, CHAUSSEE, "D908", "Boulevard de Verdun") is None


def test_meme_voie_au_dela_de_30_m_non_rattachee():
    g = _comptages(("D908", "33 boulevard de Verdun", 474.0, 2021, 31))
    assert poids_lourds.rattacher(g, CHAUSSEE, "D908", "Boulevard de Verdun") is None


def test_section_la_plus_proche_puis_la_plus_recente():
    g = _comptages(
        ("D993", "boulevard Patrick Devedjian", 532.0, 2019, 12),
        ("D993", "4 boulevard de Neuilly", 454.8, 2022, 12),
        ("D993", "loin", 100.0, 2023, 25),
    )
    s = poids_lourds.rattacher(g, CHAUSSEE, "D993", "")
    assert s.annee == 2022 and s.libelle == "4 boulevard de Neuilly"


def test_sans_comptage_non_evalue_quel_que_soit_le_type_de_route():
    for g in (None, _comptages(), _comptages(("D7", "quai", 1825.0, 2021, 200))):
        f = poids_lourds.calculer(poids_lourds.rattacher(g, CHAUSSEE, "N13", ""), 0.0)
        assert (f.effet, f.statut, f.valeur) == (1.0, "non_evalue", None)
        assert f.explication == "Poids lourds : non évalué (aucun comptage publié)"
        assert f.details == {}


def test_effet_croissant_et_borne():
    valeurs = [0, PL_EFFET_NUL, 100, 300, 750, PL_EFFET_MAX, 10_000]
    effets = [poids_lourds.effet(v) for v in valeurs]
    assert effets[0] == effets[1] == 1.0
    assert effets == sorted(effets)
    assert effets[-2] == pytest.approx(EFFET_PL_MAX) and effets[-1] == pytest.approx(EFFET_PL_MAX)
    assert all(1.0 <= e <= EFFET_PL_MAX for e in effets)


def test_bus_du_sens_retires_et_details():
    g = _comptages(("D908", "33 boulevard de Verdun", 474.0, 2021, 0))
    f = poids_lourds.calculer(poids_lourds.rattacher(g, CHAUSSEE, "D908", ""), 286.0)
    assert f.valeur == 188 and f.statut == "evalue"
    assert f.effet == pytest.approx(poids_lourds.effet(188.0))
    assert f.details == {
        "source": comptages.SOURCE_92,
        "annee": 2021,
        "troncon": "D908, 33 boulevard de Verdun",
        "pl_comptes": 474,
        "bus_retires": 286,
    }
    assert "2021" in f.explication and "hors bus" in f.explication


def test_plus_de_bus_que_de_poids_lourds_comptes():
    g = _comptages(("D12", "53 rue Gaultier", 176.0, 2023, 0))
    f = poids_lourds.calculer(poids_lourds.rattacher(g, CHAUSSEE, "D12", ""), 182.0)
    assert (f.valeur, f.effet, f.statut) == (0, 1.0, "evalue")
