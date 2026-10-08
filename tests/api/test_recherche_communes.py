"""Recherche de commune par nom (008 US1, contracts/http-api.md)."""

from __future__ import annotations

import html
import logging

import httpx
import pytest
import respx

from bitumap.api import demandes
from tests.conftest import connecter, preuve


@pytest.fixture
def agent(client, courriels):
    return connecter(client, courriels)


def _radios(page: str) -> list[str]:
    return [p.split('"', 1)[0] for p in page.split('name="insee" value="')[1:]]


def test_propositions_json(client, agent):
    reponse = client.get("/communes/recherche", params={"q": "courbe"})
    assert reponse.status_code == 200
    assert {"insee": "92026", "nom": "Courbevoie", "departement": "92"} in reponse.json()
    assert len(reponse.json()) <= 10
    assert reponse.headers["cache-control"] == "private, max-age=3600"


@pytest.mark.parametrize("q", ["co", "x" * 101, ""])
def test_propositions_vides_sans_erreur(client, agent, q):
    reponse = client.get("/communes/recherche", params={"q": q})
    assert reponse.status_code == 200 and reponse.json() == []


def test_nom_de_deux_lettres_exact(client, agent):
    assert client.get("/communes/recherche", params={"q": "us"}).json() == [
        {"insee": "95625", "nom": "Us", "departement": "95"}
    ]


def test_propositions_sans_session(client):
    reponse = client.get(
        "/communes/recherche", params={"q": "courbe"}, headers={"accept": "application/json"}
    )
    assert reponse.status_code == 401 and reponse.json()["erreur"] == "connexion_requise"


def test_page_de_choix_par_nom(client, agent):
    page = client.get("/communes", params={"q": "asnieres"}).text
    assert "Asnières-sur-Seine (92)" in page
    assert "92004" in _radios(page)
    assert 'name="altcha"' in page or "altcha-widget" in page


def test_arrondissement_par_nom(client, agent):
    page = client.get("/communes", params={"q": "paris 17"}).text
    assert "Paris 17e Arrondissement" in page and "75117" in _radios(page)


def test_hors_ile_de_france(client, agent):
    reponse = client.get("/communes", params={"q": "Lyon"})
    assert reponse.status_code == 200
    assert "le service couvre l'Île-de-France" in html.unescape(reponse.text)
    assert _radios(reponse.text) == []


def test_saisie_trop_courte(client, agent):
    page = client.get("/communes", params={"q": "co"}).text
    assert "Saisissez au moins 3 lettres" in page


def test_code_postal_dans_le_champ(client, agent, territoire):
    page = client.get("/communes", params={"q": "92400"}).text
    assert _radios(page) == ["92026"]


def test_code_postal_inconnu_dans_le_champ(client, agent, territoire):
    reponse = client.get("/communes", params={"q": "91999"})
    assert reponse.status_code == 200
    assert "Ce code postal n'existe pas." in html.unescape(reponse.text)


@pytest.mark.parametrize("panne", [httpx.ConnectError("hors service"), "500"])
def test_api_geo_en_panne(client, agent, monkeypatch, panne):
    def en_panne(code):
        if panne == "500":
            requete = httpx.Request("GET", "https://geo.api.gouv.fr/communes")
            raise httpx.HTTPStatusError(
                "500", request=requete, response=httpx.Response(500, request=requete)
            )
        raise panne

    monkeypatch.setattr(demandes, "communes_du_code_postal", en_panne)
    reponse = client.get("/communes", params={"q": "92400"})
    assert reponse.status_code == 200
    assert "cherchez par le nom de la commune" in reponse.text


def test_ancien_lien_code_postal(client, agent, territoire):
    page = client.get("/communes", params={"code_postal": "92400"}).text
    assert _radios(page) == ["92026"]


def test_choix_direct_par_insee(client, agent):
    page = client.get("/communes", params={"insee": "92026"}).text
    assert _radios(page) == ["92026"]
    assert 'value="92026" required checked' in page


def test_choix_direct_hors_liste(client, agent):
    reponse = client.get(
        "/communes", params={"insee": "69123"}, headers={"accept": "application/json"}
    )
    assert reponse.status_code == 404 and reponse.json()["erreur"] == "code_inexistant"


@respx.mock(assert_all_mocked=True)
def test_aucun_appel_reseau_pour_un_nom(client, agent):
    # respx refuse toute requête non simulée : la recherche par nom n'en fait aucune.
    assert client.get("/communes/recherche", params={"q": "courbe"}).status_code == 200
    assert client.get("/communes", params={"q": "courbe"}).status_code == 200


def test_saisie_jamais_journalisee(client, agent, caplog):
    with caplog.at_level(logging.DEBUG):
        client.get("/communes/recherche", params={"q": "saisie-temoin-zq"})
        client.get("/communes", params={"q": "saisie-temoin-zq"})
    assert "saisie-temoin-zq" not in caplog.text.replace("q=saisie-temoin-zq", "")


def test_script_servi(client):
    reponse = client.get("/statique/communes.js")
    assert reponse.status_code == 200
    assert "javascript" in reponse.headers["content-type"]


def test_accueil_propose_la_recherche(client, agent):
    page = client.get("/").text
    assert "data-recherche-communes" in page and 'src="/statique/communes.js"' in page
    assert "API Géo" in page and "Licence Ouverte" in page


def test_choix_puis_demande(client, agent, territoire, s3):
    page = client.get("/communes", params={"q": "courbe"}).text
    assert "92026" in _radios(page)
    reponse = client.post(
        "/demandes",
        data={"insee": "92026", "csrf": agent, "altcha": preuve(client)},
        follow_redirects=False,
    )
    assert reponse.status_code == 303 and reponse.headers["location"].startswith("/demandes/")
    assert "Courbevoie" in client.get(reponse.headers["location"]).text
