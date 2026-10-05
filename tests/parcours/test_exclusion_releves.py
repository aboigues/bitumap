"""Exclusion des points relevés récemment (006 T023, US4, FR-011) : relevés déposés par l'API
de 003, rapport figé de Courbevoie, géocodage et itinéraire simulés, aucun réseau."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import respx

from bitumap.db import connexion
from bitumap.parcours import itineraire
from bitumap.terrain.points import points_du_rapport
from tests.conftest import connecter, rapport_courbevoie
from tests.parcours.aides import simuler_ign
from tests.terrain.aides import JSON, deposer


@pytest.fixture
def agent(client, courriels, s3, monkeypatch):
    monkeypatch.setattr(itineraire, "LIMITEUR", itineraire.Limiteur(dormir=lambda s: None))
    empreinte = rapport_courbevoie()
    csrf = connecter(client, courriels, "agent@exemple.fr")
    points = points_du_rapport("92026", empreinte).values()
    # Critique + Sérieux, dans l'ordre du rang : 21 points, tous visités en 3 h en voiture.
    retenus = sorted((p for p in points if p.groupe in ("P1a", "P1b")), key=lambda p: p.rang)
    return csrf, [p.id for p in retenus]


def _il_y_a(jours: float) -> str:
    return (datetime.now(UTC) - timedelta(days=jours)).isoformat()


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
    return client.post(
        "/parcours/92026",
        data=donnees,
        follow_redirects=False,
        headers={"accept": "text/html, application/json"},
    )


def _resultat() -> dict:
    with connexion() as conn:
        return conn.execute(
            "SELECT resultat, exclusion_releves_jours FROM parcours ORDER BY cree_le DESC LIMIT 1"
        ).fetchone()


@respx.mock
def test_points_releves_recemment_exclus(client, agent):
    csrf, ids = agent
    recents, ancien, retire = ids[:5], ids[5], ids[6]
    for point in recents:
        assert deposer(client, csrf, point_id=point, cree_le=_il_y_a(2))[1].status_code == 201
    deposer(client, csrf, point_id=recents[0], cree_le=_il_y_a(60))  # plus ancien, même point
    assert deposer(client, csrf, point_id=ancien, cree_le=_il_y_a(40))[1].status_code == 201
    releve, _ = deposer(client, csrf, point_id=retire, cree_le=_il_y_a(1))
    reponse = client.post(f"/terrain/releves/{releve}/retrait", json={"csrf": csrf}, headers=JSON)
    assert reponse.status_code == 200
    simuler_ign()

    reponse = _demander(client, csrf, exclure_releves="1", exclusion_releves_jours="30")
    assert reponse.status_code == 303
    ligne = _resultat()
    r = ligne["resultat"]
    assert ligne["exclusion_releves_jours"] == 30
    visites = [v["point_id"] for v in r["visites"]]
    assert visites == ids[5:]  # 16 points : relevé ancien et relevé retiré ignorés
    assert {n["point_id"]: n["raison"] for n in r["non_visites"]} == dict.fromkeys(
        recents, "releve_recent"
    )
    assert r["resume"]["nb_exclus"] == 5
    # Aucune donnée de relevé (auteur, observation, niveau constaté) dans le parcours.
    assert set(r["non_visites"][0]) == {"point_id", "rang", "niveau", "raison"}
    page = client.get(reponse.headers["location"]).text
    assert "5 points exclus : relevés depuis moins de 30 jours" in page


@respx.mock
def test_option_absente_aucun_effet(client, agent):
    csrf, ids = agent
    deposer(client, csrf, point_id=ids[0], cree_le=_il_y_a(1))
    simuler_ign()
    # Nombre de jours saisi mais case décochée : l'option est ignorée.
    assert _demander(client, csrf, exclusion_releves_jours="30").status_code == 303
    ligne = _resultat()
    assert ligne["exclusion_releves_jours"] is None
    assert len(ligne["resultat"]["visites"]) == 21
    assert ligne["resultat"]["resume"]["nb_exclus"] == 0


@respx.mock
def test_tous_les_points_exclus(client, agent):
    csrf, ids = agent
    for point in ids:
        deposer(client, csrf, point_id=point, cree_le=_il_y_a(1))
    simuler_ign()
    reponse = _demander(
        client, csrf, niveaux=["P1a"], exclure_releves="1", exclusion_releves_jours="30"
    )
    assert reponse.status_code == 400 and "aucun_point" in reponse.text


@respx.mock
@pytest.mark.parametrize("jours", ["0", "366"])
def test_nombre_de_jours_borne(client, agent, jours):
    csrf, _ = agent
    simuler_ign()
    reponse = _demander(client, csrf, exclure_releves="1", exclusion_releves_jours=jours)
    assert reponse.status_code == 400 and "parametres_invalides" in reponse.text


def test_formulaire_propose_l_option(client, agent):
    page = client.get("/parcours/92026").text
    assert 'name="exclure_releves"' in page
    assert 'name="exclusion_releves_jours"' in page and 'value="30"' in page
