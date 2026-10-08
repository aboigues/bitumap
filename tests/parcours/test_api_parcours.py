"""Routes du parcours (006 T010, T017 ; contracts/http-api.md) : rapport figé de Courbevoie,
géocodage et itinéraire simulés, aucun réseau."""

from __future__ import annotations

import logging
import re

import httpx
import pytest
import respx

from bitumap.parcours import itineraire
from tests.conftest import connecter, rapport_courbevoie
from tests.parcours.aides import HOTEL_DE_VILLE, simuler_ign

CSRF = re.compile(r'name="csrf" value="([^"]+)"')


@pytest.fixture
def agent(client, courriels, s3, monkeypatch):
    """Agent connecté, rapport de Courbevoie en vigueur, IGN simulée, limiteur sans attente."""
    monkeypatch.setattr(itineraire, "LIMITEUR", itineraire.Limiteur(dormir=lambda s: None))
    rapport_courbevoie()
    return connecter(client, courriels, "agent@exemple.fr")


def _demander(client, csrf, **champs):
    donnees = {
        "csrf": csrf,
        "adresse": "2 place de l'hôtel de ville",
        "niveaux": ["P1a", "P1b"],
        "mode": "voiture",
        "duree_max_min": "180",
        "arret_min": "5",
        **champs,
    }
    # Erreurs en JSON (code stable), comme les autres tests de l'API.
    return client.post(
        "/parcours/92026",
        data=donnees,
        follow_redirects=False,
        headers={"accept": "text/html, application/json"},
    )


@respx.mock
def test_formulaire_avec_effectifs(client, agent):
    page = client.get("/parcours/92026")
    assert page.status_code == 200
    assert "Courbevoie" in page.text and "Critique (11 points)" in page.text
    assert 'value="pied"' in page.text and "velo" not in page.text  # FR-002
    assert client.get("/parcours/75056").status_code == 404  # aucun rapport


@respx.mock
def test_boucle_dans_l_ordre_du_rang(client, agent, caplog):
    simuler_ign()
    with caplog.at_level(logging.DEBUG):
        reponse = _demander(client, agent)
    assert reponse.status_code == 303
    page = client.get(reponse.headers["location"])
    assert page.status_code == 200 and "Télécharger le GPX" in page.text
    ordres = [int(x) for x in re.findall(r"<strong>(\d+) · ", page.text)]
    rangs = [int(x) for x in re.findall(r"rang (\d+) · ", page.text)]
    assert ordres == list(range(1, len(ordres) + 1)) and rangs == sorted(rangs)
    assert len(ordres) == 21  # Critique + Sérieux tiennent en 3 h en voiture
    # L'adresse de départ n'apparaît dans aucun journal (FR-012).
    assert "Hôtel De Ville" not in caplog.text and "hôtel de ville" not in caplog.text


@respx.mock
def test_duree_courte_points_non_visites(client, agent):
    simuler_ign()
    page = client.get(_demander(client, agent, duree_max_min="45").headers["location"]).text
    assert "Non visités, pour une prochaine tournée" in page
    resume = re.search(r"reste (\d+) min sur 45 min", page)
    assert resume is not None
    assert re.search(r"\d+,\d km", page)  # décimales à la française


@respx.mock
def test_adresse_ambigue_propositions(client, agent):
    simuler_ign(
        adresses=(HOTEL_DE_VILLE, ("2 Place De L'Hôtel De Ville 92800 Puteaux", 2.24, 48.88, 0.94))
    )
    reponse = _demander(client, agent)
    assert reponse.status_code == 400 and "plusieurs adresses correspondent" in reponse.text
    assert reponse.text.count('name="choix"') == 2
    suite = _demander(client, agent, choix="0")
    assert suite.status_code == 303


@respx.mock
@pytest.mark.parametrize(
    ("champs", "statut", "code"),
    [
        ({"niveaux": ["P9"]}, 400, "parametres_invalides"),
        ({"mode": "velo"}, 400, "parametres_invalides"),
        ({"duree_max_min": "20"}, 400, "parametres_invalides"),
        ({"duree_max_min": "30", "arret_min": "30"}, 400, "duree_insuffisante"),
    ],
)
def test_erreurs(client, agent, champs, statut, code):
    simuler_ign()
    reponse = _demander(client, agent, **champs)
    assert reponse.status_code == statut and code in reponse.text


@respx.mock
def test_depart_trop_loin(client, agent):
    simuler_ign(adresses=(("Place Bellecour 69002 Lyon", 4.832, 45.757, 0.95),))
    reponse = _demander(client, agent)
    assert reponse.status_code == 400 and "depart_trop_loin" in reponse.text


@respx.mock
def test_itineraire_indisponible_aucun_parcours(client, agent, monkeypatch):
    monkeypatch.setattr("bitumap.sources.base.time.sleep", lambda s: None)
    simuler_ign()
    respx.get(itineraire.URL).mock(return_value=httpx.Response(503))
    reponse = _demander(client, agent)
    assert reponse.status_code == 503 and "itineraire_indisponible" in reponse.text
    from bitumap.db import connexion

    with connexion() as conn:
        assert conn.execute("SELECT count(*) AS n FROM parcours").fetchone()["n"] == 0


@respx.mock
def test_quota_de_20_par_jour(client, agent, monkeypatch):
    from bitumap.api import parcours as routes

    monkeypatch.setattr(routes, "QUOTA_PARCOURS", 2)
    simuler_ign()
    assert _demander(client, agent).status_code == 303
    assert _demander(client, agent).status_code == 303
    reponse = _demander(client, agent)
    assert reponse.status_code == 429 and "quota_parcours" in reponse.text


@respx.mock
def test_csrf_et_session(client, agent):
    simuler_ign()
    assert _demander(client, "faux").status_code == 403
    client.cookies.clear()
    reponse = client.get("/parcours/92026", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/?motif=session&suite=%2Fparcours%2F92026"


@respx.mock
def test_resultat_et_gpx_reserves_au_compte(client, courriels, agent):
    simuler_ign()
    lien = _demander(client, agent).headers["location"]
    gpx = client.get(lien + ".gpx")
    assert gpx.status_code == 200
    assert gpx.headers["content-type"].startswith("application/gpx+xml")
    assert re.match(
        r'attachment; filename="parcours-92026-\d{4}-\d{2}-\d{2}\.gpx"',
        gpx.headers["content-disposition"],
    )
    client.cookies.clear()
    connecter(client, courriels, "autre@exemple.fr")
    assert client.get(lien).status_code == 404
    assert client.get(lien + ".gpx").status_code == 404
    assert client.get("/parcours/resultat/pas-un-uuid").status_code == 404


@respx.mock
def test_adresses_json(client, agent):
    simuler_ign()
    reponse = client.get("/parcours/adresses", params={"q": "2 place", "insee": "92026"})
    assert reponse.status_code == 200
    assert reponse.json()[0]["libelle"] == HOTEL_DE_VILLE[0]
    assert client.get("/parcours/adresses", params={"q": "ab"}).status_code == 400
