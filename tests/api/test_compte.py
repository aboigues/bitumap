"""Compte et données personnelles (FR-026, FR-027) : suppression, purge, information RGPD."""

import re

from bitumap.db import connexion
from bitumap.db.purge import purger
from tests.conftest import connecter, demander_lien, preuve


def _nb(table: str) -> int:
    with connexion() as conn:
        return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608


def test_suppression_du_compte(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    client.post(
        "/demandes",
        data={"insee": "92026", "csrf": csrf, "altcha": preuve(client)},
        follow_redirects=False,
    )
    demander_lien(client, "agent@exemple.fr")  # lien encore non validé
    reponse = client.post(
        "/compte/suppression",
        data={"csrf": csrf, "confirmation": "SUPPRIMER"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    assert "__Host-session=" in reponse.headers["set-cookie"]
    for table in ("compte", "session", "lien_connexion", "demandeur_demande"):
        assert _nb(table) == 0, table
    assert _nb("demande") == 1  # la demande reste en file, sans donnée personnelle
    assert "Votre compte a été supprimé" in client.get(reponse.headers["location"]).text


def test_suppression_exige_confirmation_et_csrf(client, courriels):
    csrf = connecter(client, courriels)
    assert client.post("/compte/suppression", data={"csrf": csrf}).status_code == 400
    faux = {"csrf": "faux", "confirmation": "SUPPRIMER"}
    assert client.post("/compte/suppression", data=faux).status_code == 403
    assert _nb("compte") == 1


def test_suppression_exige_une_session(client):
    reponse = client.post("/compte/suppression", data={"confirmation": "SUPPRIMER"})
    assert reponse.status_code == 401


def test_page_compte(client, courriels):
    connecter(client, courriels)
    page = client.get("/compte").text
    assert "agent@exemple.fr" in page and 'action="/compte/suppression"' in page


def test_information_rgpd_avant_creation_du_compte(client):
    accueil = client.get("/").text
    assert 'href="/confidentialite"' in accueil and "12 mois" in accueil
    page = client.get("/confidentialite")
    assert page.status_code == 200
    for attendu in ("finalité", "12 mois", "24 heures", "supprimer votre compte", "CNIL"):
        assert attendu.lower() in page.text.lower(), attendu


def test_widget_auto_heberge(client):
    accueil = client.get("/").text
    sources = re.findall(r'<script[^>]*src="([^"]+)"', accueil)
    assert sources and all(s.startswith("/statique/altcha/") for s in sources)
    assert 'challenge="/altcha/defi"' in accueil
    for src in sources:
        assert client.get(src).status_code == 200
    assert "script-src 'self'" in client.get("/").headers["content-security-policy"]


def test_fichiers_du_widget_conformes():
    from tools.verifier_altcha import verifier_local

    assert verifier_local() == []


def test_purge(client, courriels):
    connecter(client, courriels, "ancien@exemple.fr")
    demander_lien(client, "b@exemple.fr")
    with connexion() as conn:
        conn.execute("UPDATE compte SET derniere_connexion = now() - interval '13 months'")
        conn.execute("UPDATE preuve_antibot SET utilisee_le = now() - interval '2 hours'")
        conn.execute("UPDATE compteur_quota SET expire_le = now() - interval '1 second'")
        conn.execute(
            "UPDATE lien_connexion SET expire_le = now() - interval '2 days'"
            " WHERE email = 'b@exemple.fr'"
        )
    resultat = purger()
    assert resultat["comptes_inactifs"] == 1
    for table in ("compte", "session", "preuve_antibot", "compteur_quota", "lien_connexion"):
        assert _nb(table) == 0, table
