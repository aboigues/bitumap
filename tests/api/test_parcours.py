"""Parcours complet (quickstart §2) : connexion → commune → demande → lot → rapport."""

from bitumap.db import connexion
from tests.conftest import connecter, preuve
from tests.lot.aides import executer_lot


def _demander(client, csrf, insee="92026"):
    return client.post(
        "/demandes",
        data={"insee": insee, "csrf": csrf, "altcha": preuve(client)},
        follow_redirects=False,
    )


def test_code_postal_une_commune(client, courriels, territoire):
    connecter(client, courriels)
    page = client.get("/communes", params={"code_postal": "92400"}).text
    assert "Courbevoie" in page


def test_code_postal_plusieurs_communes(client, courriels, territoire):
    connecter(client, courriels)
    page = client.get("/communes", params={"code_postal": "95000"}).text
    assert "4 communes" in page and "Pontoise" in page


def test_codes_refuses(client, courriels, territoire):
    connecter(client, courriels)
    entetes = {"accept": "application/json"}
    for code, attendu in (
        ("69001", "hors_ile_de_france"),
        ("9240", "format_invalide"),
        ("91999", "code_inexistant"),
    ):
        r = client.get("/communes", params={"code_postal": code}, headers=entetes)
        assert r.json()["erreur"] == attendu


def test_parcours_complet(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    r = _demander(client, csrf)
    assert r.status_code == 303 and r.headers["location"].startswith("/demandes/")
    suivi = client.get(r.headers["location"]).text
    assert "position <strong>1</strong>" in suivi

    resultats = executer_lot()
    assert [x.statut for x in resultats] == ["terminee"]
    assert any("Rapport prêt : Courbevoie" in c.sujet for c in courriels)

    suivi = client.get(r.headers["location"]).text
    lien = suivi.split('href="/rapports/', 1)[1].split('"', 1)[0]
    rapport = client.get(f"/rapports/{lien}")
    assert rapport.status_code == 200
    assert "Courbevoie" in rapport.text
    assert "script-src 'sha256-" in rapport.headers["content-security-policy"]
    assert rapport.headers["cache-control"] == "private, no-store"
    assert client.get(f"/rapports/{lien}/points.geojson").json()["type"] == "FeatureCollection"


def test_rapport_en_cache_servi_immediatement(client, courriels, territoire, s3):
    csrf = connecter(client, courriels, "premier@exemple.fr")
    _demander(client, csrf)
    executer_lot()
    client.cookies.clear()
    csrf = connecter(client, courriels, "second@exemple.fr")
    r = _demander(client, csrf)
    assert r.status_code == 303 and r.headers["location"].startswith("/rapports/92026/")
    with connexion() as conn:
        assert conn.execute("SELECT count(*) AS n FROM demande").fetchone()["n"] == 1


def test_demandes_concurrentes_rattachees(client, courriels, territoire, s3):
    csrf = connecter(client, courriels, "a@exemple.fr")
    premiere = _demander(client, csrf).headers["location"]
    client.cookies.clear()
    csrf = connecter(client, courriels, "b@exemple.fr")
    seconde = _demander(client, csrf).headers["location"]
    assert premiere == seconde
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT compte_quota FROM demandeur_demande ORDER BY compte_quota DESC"
        ).fetchall()
    assert [x["compte_quota"] for x in lignes] == [True, False]
    executer_lot()
    destinataires = {c.destinataire for c in courriels if c.sujet.startswith("Rapport prêt")}
    assert destinataires == {"a@exemple.fr", "b@exemple.fr"}


def test_rapport_refuse_sans_session(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    _demander(client, csrf)
    executer_lot()
    lien = client.get("/demandes").text.split('href="/rapports/', 1)[1].split('"', 1)[0]
    client.cookies.clear()
    assert client.get(f"/rapports/{lien}").status_code == 401


def test_suivi_d_une_demande_d_un_autre_compte(client, courriels, territoire, s3):
    csrf = connecter(client, courriels, "a@exemple.fr")
    lien = _demander(client, csrf).headers["location"]
    client.cookies.clear()
    connecter(client, courriels, "b@exemple.fr")
    assert client.get(lien).status_code == 404


def test_commune_invalide(client, courriels, territoire):
    csrf = connecter(client, courriels)
    assert _demander(client, csrf, "99999").status_code == 400
    assert _demander(client, csrf, "../x").status_code == 400
