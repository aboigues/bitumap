"""Adaptateur des comptages poids lourds (004 T030, R5) : catalogue ``comptages.toml`` et
lecteurs génériques, réponses HTTP simulées, aucun réseau ; Courbevoie figée pour la capture
réelle."""

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
from bitumap.sources.base import SourceIndisponible
from bitumap.sources.fournisseur import FournisseurFige

COURBEVOIE = (2.233, 48.886, 2.277, 48.914)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"


def _source(ident: str) -> dict:
    return next(s for s in comptages.catalogue() if s["id"] == ident)


def test_catalogue():
    sources = comptages.catalogue()
    assert [s["id"] for s in sources] == ["cd92", "rrn"]
    for s in sources:
        assert s["type"] in comptages.LECTEURS
        assert {"etiquette", "nom", "licence", "page", "portee", "champs"} <= s.keys()
        assert {"numero", "annee"} <= s["champs"].keys()
        assert "sens" in s["champs"] or {"tmja_deux_sens", "pct_pl"} <= s["champs"].keys()


def test_type_inconnu_refuse(monkeypatch):
    monkeypatch.setattr(comptages, "LECTEURS", {"opendatasoft": comptages.lire_opendatasoft})
    with pytest.raises(ValueError, match="type inconnu pour rrn"):
        comptages.catalogue()


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
def test_opendatasoft_par_sens():
    source = _source("cd92")
    route = respx.get(comptages.url_opendatasoft(source)).mock(
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
        e = comptages.lire_opendatasoft(source, COURBEVOIE, client)
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
    assert set(g.source) == {"Hauts-de-Seine"}
    assert e.provenance.nom == source["nom"] and not e.provenance.hors_ue


@respx.mock
def test_nouveau_departement_sans_code():
    """Un département publiant sur Opendatasoft s'ajoute au catalogue : total des deux sens et
    % de poids lourds, champs propres au jeu."""
    source = {
        "id": "cd00",
        "etiquette": "Département fictif",
        "nom": "Département fictif : comptages",
        "type": "opendatasoft",
        "portail": "https://portail.exemple.test",
        "jeu": "comptages",
        "geometrie": "shape",
        "licence": "Licence Ouverte",
        "page": "https://portail.exemple.test/comptages",
        "portee": "communale",
        "champs": {
            "numero": "route",
            "annee": "annee",
            "tmja_deux_sens": "mja",
            "pct_pl": "part_pl",
        },
    }
    route = respx.get(comptages.url_opendatasoft(source)).mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[2.3, 48.8], [2.31, 48.81]],
                        },
                        "properties": {"route": "D 920", "annee": 2024, "mja": 20000, "part_pl": 6},
                    }
                ],
            },
        )
    )
    with httpx.Client() as client:
        provenances, g = comptages.acquerir(COURBEVOIE, client, [source])
    assert "intersects(shape" in route.calls[0].request.url.params["where"]
    assert [p.nom for p in provenances] == ["Département fictif : comptages"]
    assert g.numeros.tolist() == ["D920"] and g.pl_sens.tolist() == [600.0]


@respx.mock
def test_departement_sans_comptage_publie():
    """Paris, 77, 78, 91, 93, 94, 95 (inventaire T003) : le jeu du 92 ne renvoie rien."""
    source = _source("cd92")
    respx.get(comptages.url_opendatasoft(source)).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    )
    with httpx.Client() as client:
        g = comptages.lire_opendatasoft(source, (2.33, 48.85, 2.36, 48.87), client).donnees
    assert g.empty and list(g.columns[:-1]) == comptages.COLONNES


def _archive(tmp_path: Path, lignes: list[dict], champ_pl: str = "pctPL") -> bytes:
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
def test_datagouv_dernier_millesime(tmp_path):
    source = _source("rrn")
    respx.get(comptages.URL_DATAGOUV.format(jeu=source["jeu"])).mock(
        return_value=httpx.Response(
            200,
            json={
                "resources": [
                    {
                        "title": "TMJA_RRNc_2024_shp",
                        "url": "https://static.data.gouv.fr/resources/tmja/2024.zip",
                    },
                    {
                        "title": "TMJA_RRNc_2024",
                        "url": "https://static.data.gouv.fr/resources/tmja/2024.csv",
                    },
                    {
                        "title": "TMJA_2019_shp",
                        "url": "https://static.data.gouv.fr/resources/tmja/2019.zip",
                    },
                ]
            },
        )
    )
    archive = _archive(
        tmp_path,
        [
            _section_rrn("A0014", 31024, 4.46),
            _section_rrn("A0005A", 40000, 12.0),
            _section_rrn("N0013", 29700, 46.0 * 10),  # % fautif (cf. 2019, LL-018) : écarté
            _section_rrn("A0086", 92091, 0.0),  # sans % de poids lourds : écarté
            _section_rrn("A0001", 96596, 17.2, x=700000.0),  # hors de l'emprise
        ],
    )
    telechargement = respx.get("https://static.data.gouv.fr/resources/tmja/2024.zip").mock(
        return_value=httpx.Response(200, content=archive)
    )
    with httpx.Client() as client:
        e = comptages.lire_datagouv_shapefile(source, COURBEVOIE, client)
    assert telechargement.called and e.provenance.nom.endswith("national (2024)")
    g = e.donnees
    assert g.numeros.tolist() == ["A14", "A5A"] and g.troncon.tolist() == ["A14", "A5A"]
    # Trafic des deux sens confondus : chaque sens en porte la moitié.
    assert g.pl_sens.tolist() == [round(31024 * 4.46 / 100 / 2, 1), 2400.0]
    assert g.annee.tolist() == [2024, 2024]
    assert set(g.source) == {"Réseau routier national"}


def test_champs_des_anciens_millesimes(tmp_path):
    archive = tmp_path / "rrn.zip"
    archive.write_bytes(
        _archive(tmp_path, [_section_rrn("N0118", 54200, 6.7, annee=2018)], "ratio_PL")
    )
    g = comptages.lire_archive(_source("rrn"), archive, (640000, 6860000, 650000, 6870000))
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
    assert len(g) >= 40 and set(g.source) == {"Hauts-de-Seine"}
    assert g.pl_sens.between(0, 5000).all() and g.annee.between(2014, 2026).all()


@respx.mock
def test_archive_hors_de_data_gouv_refusee():
    """Lien de ressource imposé par une réponse altérée : refusé avant tout téléchargement."""
    source = _source("rrn")
    respx.get(comptages.URL_DATAGOUV.format(jeu=source["jeu"])).mock(
        return_value=httpx.Response(
            200, json={"resources": [{"title": "TMJA_2025_shp", "url": "http://10.0.0.1/x.zip"}]}
        )
    )
    with httpx.Client() as client, pytest.raises(SourceIndisponible, match="URL refusée"):
        comptages.lire_datagouv_shapefile(source, COURBEVOIE, client)
