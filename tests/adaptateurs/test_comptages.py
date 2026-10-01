"""Adaptateur des comptages poids lourds (004 T030, R5) : réponses HTTP simulées, aucun
réseau ; Courbevoie figée pour la capture réelle."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx
import pytest
import respx
from shapely.geometry import LineString

from bitumap.sources import comptages
from bitumap.sources.fournisseur import FournisseurFige

COURBEVOIE = (2.233, 48.886, 2.277, 48.914)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"


def _section_92(nom_voie, adresse, annee, s1, s2, coords=((2.25, 48.90), (2.251, 48.901))):
    (tmja_s1, pl_s1), (tmja_s2, pl_s2) = s1, s2
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]},
        "properties": {
            "nom_voie": nom_voie,
            "adresse_compteur": adresse,
            "annee_comptage": annee,
            "tmja_s1": tmja_s1,
            "tmja_s2": tmja_s2,
            "pourcentage_pl_s1": pl_s1,
            "pourcentage_pl_s2": pl_s2,
        },
    }


@respx.mock
def test_hauts_de_seine_normalises():
    route = respx.get(comptages.URL_92).mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _section_92("RD7", "23 quai Paul Doumer", "2021", (21572, 8.46), (21169, 6.93)),
                    _section_92("RD9", "boulevard Saint-Denis", "2011", (3473, None), (4580, None)),
                    _section_92("RD993", "4 bd de Neuilly", "2022", (8918, 5.1), (None, None)),
                    _section_92("A14, RN1014", "A14-Y", "2022", (48712, 5.37), (26793, 4.16)),
                    _section_92("RD1", "quai", "2021", (1000, 120.0), (1000, 0.0)),
                ],
            },
        )
    )
    with httpx.Client() as client:
        e = comptages.hauts_de_seine(COURBEVOIE, client)
    assert "intersects(geo_shape" in route.calls[0].request.url.params["where"]
    g = e.donnees
    assert g.crs == "EPSG:2154"
    assert list(g.columns[:-1]) == comptages.COLONNES
    # Sens le plus chargé ; sans % de poids lourds publié, ou hors de ]0, 100] : écarté.
    assert g.troncon.tolist() == [
        "RD7, 23 quai Paul Doumer",
        "RD993, 4 bd de Neuilly",
        "A14, RN1014, A14-Y",
    ]
    assert g.pl_sens.tolist() == [1825.0, 454.8, 2615.8]
    assert g.annee.tolist() == [2021, 2022, 2022]
    assert g.numeros.tolist() == ["D7", "D993", "A14;N1014"]
    assert set(g.source) == {comptages.SOURCE_92}
    assert e.provenance.licence == comptages.LICENCE and not e.provenance.hors_ue


@respx.mock
def test_departement_sans_comptage_publie():
    """Paris, 77, 78, 91, 93, 94, 95 (inventaire T003) : le jeu du 92 ne renvoie rien."""
    respx.get(comptages.URL_92).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    )
    with httpx.Client() as client:
        g = comptages.hauts_de_seine((2.33, 48.85, 2.36, 48.87), client).donnees
    assert g.empty and list(g.columns[:-1]) == comptages.COLONNES


def _archive_rrn(tmp_path: Path, lignes: list[dict], champ_pl: str = "pctPL") -> bytes:
    gdf = gpd.GeoDataFrame(
        [{k: v for k, v in ligne.items() if k != "geometry"} for ligne in lignes],
        geometry=[ligne["geometry"] for ligne in lignes],
        crs="EPSG:2154",
    ).rename(columns={"pctPL": champ_pl})
    dossier = tmp_path / "shp"
    dossier.mkdir()
    gdf.to_file(dossier / "TMJA.shp")
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for f in dossier.iterdir():
            z.write(f, f.name)
    return tampon.getvalue()


def _section_rrn(route, tmja, part, x=645000.0, annee=2024):
    return {
        "route": route,
        "anneeMesur": annee,
        "tmja": tmja,
        "pctPL": part,
        "geometry": LineString([(x, 6866000.0), (x + 500, 6866500.0)]),
    }


@respx.mock
def test_reseau_national_dernier_millesime(tmp_path):
    respx.get(comptages.URL_RRN).mock(
        return_value=httpx.Response(
            200,
            json={
                "resources": [
                    {"title": "TMJA_RRNc_2024_shp", "url": "https://exemple.test/2024.zip"},
                    {"title": "TMJA_RRNc_2024", "url": "https://exemple.test/2024.csv"},
                    {"title": "TMJA_2019_shp", "url": "https://exemple.test/2019.zip"},
                ]
            },
        )
    )
    archive = _archive_rrn(
        tmp_path,
        [
            _section_rrn("A0014", 31024, 4.46),
            _section_rrn("A0005A", 40000, 12.0),
            _section_rrn("N0013", 29700, 46.0 * 10),  # % fautif (cf. 2019) : écarté
            _section_rrn("A0086", 92091, 0.0),  # sans % de poids lourds : écarté
            _section_rrn("A0001", 96596, 17.2, x=700000.0),  # hors de l'emprise
        ],
    )
    telechargement = respx.get("https://exemple.test/2024.zip").mock(
        return_value=httpx.Response(200, content=archive)
    )
    with httpx.Client() as client:
        e = comptages.reseau_national(COURBEVOIE, client)
    assert telechargement.called and "(2024)" in e.provenance.nom
    g = e.donnees
    assert g.numeros.tolist() == ["A14", "A5A"]
    # Trafic des deux sens confondus : chaque sens en porte la moitié.
    assert g.pl_sens.tolist() == [round(31024 * 4.46 / 100 / 2, 1), 2400.0]
    assert g.annee.tolist() == [2024, 2024]
    assert set(g.source) == {comptages.SOURCE_RRN}


def test_reseau_national_champs_des_anciens_millesimes(tmp_path):
    archive = tmp_path / "rrn.zip"
    archive.write_bytes(
        _archive_rrn(tmp_path, [_section_rrn("N0118", 54200, 6.7, annee=2018)], "ratio_PL")
    )
    g = comptages.lire_reseau_national(archive, (640000, 6860000, 650000, 6870000))
    assert g.numeros.tolist() == ["N118"] and g.annee.tolist() == [2018]


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [("RD9B", ["D9B"]), ("A14, RN1014", ["A14", "N1014"]), ("N0013", ["N13"]), (None, [])],
)
def test_numeros(texte, attendu):
    assert comptages.numeros(texte) == attendu


def test_courbevoie_figee():
    provenances, g = FournisseurFige(FIXTURES, "92026").comptages_pl(None)
    assert [p.nom.split(" :")[0] for p in provenances] == [
        "Département des Hauts-de-Seine",
        "Ministère chargé des transports",
    ]
    assert len(g) >= 40 and set(g.source) == {comptages.SOURCE_92}
    assert g.pl_sens.between(0, 5000).all() and g.annee.between(2014, 2026).all()
