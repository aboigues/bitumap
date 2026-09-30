"""Dépôt d'un relevé (003 US1, T012) : idempotence, bornes, quota, copie du point."""

import pytest

from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain.aides import JSON, POINT, deposer


@pytest.fixture
def agent(client, courriels, s3):
    rapport_courbevoie()
    return connecter(client, courriels)


def _nb(table):
    with connexion() as conn:
        return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608


def test_creation_puis_idempotence(client, agent):
    releve_id, reponse = deposer(client, agent, profondeur_mm=18, instrument="règle et cale")
    assert reponse.status_code == 201 and reponse.json()["version"] == 1
    _, rejoue = deposer(client, agent, releve_id=releve_id)
    assert rejoue.status_code == 200 and rejoue.json()["deja_enregistre"]
    assert _nb("releve") == 1 and _nb("releve_version") == 1


def test_copie_du_point_a_la_saisie(client, agent):
    releve_id, _ = deposer(client, agent)
    with connexion() as conn:
        r = conn.execute("SELECT * FROM releve WHERE id = %s", (releve_id,)).fetchone()
    assert r["point_nom"] == "Paix - Verdun"
    assert r["point_designation"].startswith("Paix - Verdun · vers")
    assert r["niveau_estime"].startswith("P")


def test_identifiant_d_un_autre_compte(client, courriels, agent):
    releve_id, _ = deposer(client, agent)
    client.cookies.clear()
    autre = connecter(client, courriels, "autre@exemple.fr")
    _, reponse = deposer(client, autre, releve_id=releve_id)
    assert reponse.status_code == 409 and reponse.json()["erreur"] == "identifiant_pris"


def test_niveau_requis(client, agent):
    _, reponse = deposer(client, agent, niveau=None)
    assert reponse.status_code == 400 and reponse.json()["erreur"] == "niveau_requis"


@pytest.mark.parametrize(
    "champs",
    [
        {"niveau": "effondre"},
        {"profondeur_mm": 201, "instrument": "règle"},
        {"profondeur_mm": 12},  # instrument requis
        {"observation": "x" * 1001},
        {"annee_refection": 1949, "source_refection": "constatee"},
        {"annee_refection": 2999, "source_refection": "constatee"},
        {"annee_refection": 2019},  # source requise
        {"source_refection": "rumeur", "annee_refection": 2019},
        {"cree_le": "2019-01-01T00:00:00+00:00"},
        {"lon": 2.26},  # position incomplète
    ],
)
def test_bornes_du_modele(client, agent, champs):
    _, reponse = deposer(client, agent, **champs)
    assert reponse.status_code == 400 and reponse.json()["erreur"] == "saisie_invalide"


def test_point_hors_rapport(client, agent):
    _, reponse = deposer(client, agent, point_id="A999999999")
    assert reponse.status_code == 404 and reponse.json()["erreur"] == "point_inconnu"


def test_csrf_obligatoire(client, agent):
    _, reponse = deposer(client, "faux")
    assert reponse.status_code == 403


def test_sans_session(client, s3):
    rapport_courbevoie()
    _, reponse = deposer(client, "x")
    assert reponse.status_code == 401


def test_quota_quotidien(client, agent, monkeypatch):
    monkeypatch.setattr(reglages(), "quota_releves_compte_jour", 2)
    for _ in range(2):
        assert deposer(client, agent)[1].status_code == 201
    _, reponse = deposer(client, agent)
    assert reponse.status_code == 429 and reponse.json()["erreur"] == "quota_releves"


def test_position_eloignee(client, agent):
    _, pres = deposer(client, agent, lon=2.26057, lat=48.90077)
    _, loin = deposer(client, agent, lon=2.2700, lat=48.9100)
    assert pres.json()["position_eloignee"] is False
    assert loin.json()["position_eloignee"] is True


def test_pages_de_terrain(client, agent):
    liste = client.get("/terrain/92026")
    assert liste.status_code == 200 and "Paix - Verdun" in liste.text
    assert "geolocation=(self)" in liste.headers["permissions-policy"]
    assert "connect-src 'self' http" in liste.headers["content-security-policy"]
    fiche = client.get(f"/terrain/92026/{POINT}")
    assert fiche.status_code == 200 and 'name="niveau"' in fiche.text
    assert client.get("/terrain/92004", headers=JSON).json()["erreur"] == "rapport_absent"
    assert client.get("/terrain/manifeste.webmanifest").status_code == 200
