"""Adaptateurs de sources, réponses HTTP simulées (T023) : pagination, valeurs manquantes,
licences et provenance."""

import io
from datetime import date

import httpx
import pytest
import respx
from PIL import Image

from bitumap.facteurs import voirie
from bitumap.sources import altimetrie, base, bdtopo, chaleur, idfm, ortho, osm, panoramax
from bitumap.sources.base import client_http


def _entite(i, props=None, coords=(2.27, 48.9)):
    return {
        "type": "Feature",
        "properties": {"cleabs": f"T{i}", **(props or {})},
        "geometry": {"type": "Point", "coordinates": list(coords)},
    }


@respx.mock
def test_bdtopo_pagination(monkeypatch):
    monkeypatch.setattr(bdtopo, "PAGE", 2)
    pages = {
        0: [_entite(0, {"cpx_numero": "D9"}), _entite(1)],
        2: [_entite(2)],
    }

    def repondre(requete):
        debut = int(requete.url.params["STARTINDEX"])
        couche = requete.url.params["TYPENAMES"]
        entites = pages.get(debut, []) if "troncon" in couche else []
        return httpx.Response(200, json={"type": "FeatureCollection", "features": entites})

    respx.get(bdtopo.URL_WFS).mock(side_effect=repondre)
    e = bdtopo.acquerir((2.2, 48.8, 2.3, 48.9))
    assert len(e.donnees["troncons"]) == 3
    assert e.provenance.licence == "Licence Ouverte Etalab 2.0"


@respx.mock
def test_altimetrie_valeur_inconnue():
    respx.get(altimetrie.URL).mock(
        return_value=httpx.Response(200, json={"elevations": [43.25, -99999]})
    )
    assert altimetrie.altitudes([(2.27, 48.9), (2.28, 48.9)]) == [43.25, None]


@respx.mock
def test_chaleur_pagination(monkeypatch):
    monkeypatch.setattr(chaleur, "PAGE", 1)
    appels = []

    def repondre(requete):
        decalage = int(requete.url.params["resultOffset"])
        appels.append(decalage)
        entites = [_entite(decalage, {"aleaj_note": 9, "type_lcz": "8"})] if decalage < 2 else []
        return httpx.Response(200, json={"type": "FeatureCollection", "features": entites})

    respx.get(chaleur.URL).mock(side_effect=repondre)
    e = chaleur.acquerir((2.2, 48.8, 2.3, 48.9))
    assert len(e.donnees) == 2 and appels == [0, 1, 2]
    assert e.provenance.date_extraction == date(2022, 1, 1)


@respx.mock
def test_panoramax_plus_recente_dans_le_rayon():
    def photo(ident, lon, jour, licence="CC-BY-SA-4.0"):
        return {
            "id": ident,
            "geometry": {"type": "Point", "coordinates": [lon, 48.9]},
            "properties": {"datetime": f"{jour}T10:00:00+00:00", "license": licence},
        }

    respx.get(panoramax.URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    photo("ancienne", 2.27, "2020-06-27"),
                    photo("recente", 2.27005, "2025-02-19", "etalab-2.0"),
                    photo("trop_loin", 2.2710, "2026-01-01"),  # ≈ 73 m
                ]
            },
        )
    )
    p = panoramax.photo_la_plus_recente(2.27, 48.9, 30)
    assert p.id == "recente" and p.licence == "etalab-2.0" and p.distance_m < 30


@respx.mock
def test_ortho_image_uniforme_ignoree():
    uniforme = io.BytesIO()
    Image.new("RGB", (16, 16), (255, 255, 255)).save(uniforme, format="JPEG")
    respx.get(ortho.URL_WMS).mock(
        return_value=httpx.Response(
            200, content=uniforme.getvalue(), headers={"content-type": "image/jpeg"}
        )
    )
    with client_http() as client:
        assert ortho.image("ORTHOIMAGERY.ORTHOPHOTOS2003", 2.27, 48.9, 40, 16, client) is None


def test_feu_pieton_reconnu():
    assert osm.est_feu_pieton({"crossing": "traffic_signals"})
    assert osm.est_feu_pieton({"traffic_signals": "crossing_only"})
    assert not osm.est_feu_pieton({"highway": "traffic_signals"})


def test_revetement_rigide():
    assert osm.est_rigide("paving_stones") and not osm.est_rigide("asphalt")


def test_normalisation_des_numeros_de_route():
    assert voirie.normaliser_numero("D 9b") == "D9B"
    assert voirie.normaliser_numero("RD 908") == "D908"
    assert voirie.classement_osm("N 13") == "nationale"
    assert voirie.classement_osm("Avenue") is None


@pytest.mark.parametrize(
    ("insee", "attendu"), [("75117", "75056"), ("75101", "75056"), ("92004", "92004")]
)
def test_offre_d_un_arrondissement_de_paris(insee, attendu):
    # IDFM rattache toute l'offre de Paris à 75056 : un arrondissement n'y figure pas.
    assert idfm.code_commune_offre(insee) == attendu


@respx.mock
def test_offre_d_un_arrondissement_demandee_pour_paris(tmp_path):
    from bitumap.sources.fournisseur import FournisseurEnLigne

    respx.get(idfm.URL).mock(
        return_value=httpx.Response(200, json={"metas": {"default": {"modified": "2026-03-31"}}})
    )
    route = respx.get(f"{idfm.URL}/exports/json").mock(return_value=httpx.Response(200, json=[]))
    FournisseurEnLigne("75117", tmp_path / "osm.gpkg", date(2026, 9, 27)).offre()
    assert 'code_commune="75056"' in route.calls.last.request.url.params["where"]


def test_cause_lisible_d_un_echec():
    assert base.cause(base.SourceIndisponible("Orthophotos IGN", "HTTP 429")) == (
        "Orthophotos IGN : HTTP 429"
    )
    # Autre exception : son type seulement, jamais son message (adresse, clé…).
    assert base.cause(RuntimeError("https://exemple/?cle=secret")) == "RuntimeError"
