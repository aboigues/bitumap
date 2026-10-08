"""Connexion par lien e-mail (FR-006, FR-006b, SC-010)."""

from bitumap.db import connexion
from tests.conftest import connecter, demander_lien


def _jeton(courriels):
    return courriels[-1].texte.split("/connexion/", 1)[1].split()[0]


def test_lien_valide_ouvre_une_session(client, courriels):
    csrf = connecter(client, courriels)
    assert csrf
    assert "Se déconnecter" in client.get("/").text


def test_lien_reutilise_refuse(client, courriels):
    demander_lien(client, "a@exemple.fr")
    jeton = _jeton(courriels)
    assert client.get(f"/connexion/{jeton}", follow_redirects=False).status_code == 303
    client.cookies.clear()
    assert client.get(f"/connexion/{jeton}", follow_redirects=False).status_code == 410


def test_lien_expire_refuse(client, courriels):
    demander_lien(client, "a@exemple.fr")
    with connexion() as conn:
        conn.execute("UPDATE lien_connexion SET expire_le = now() - interval '1 minute'")
    assert client.get(f"/connexion/{_jeton(courriels)}", follow_redirects=False).status_code == 410


def test_jeton_jamais_stocke_en_clair(client, courriels):
    demander_lien(client, "a@exemple.fr")
    jeton = _jeton(courriels)
    with connexion() as conn:
        stocke = conn.execute("SELECT empreinte_jeton FROM lien_connexion").fetchone()
    assert jeton.encode() not in bytes(stocke["empreinte_jeton"])
    assert len(bytes(stocke["empreinte_jeton"])) == 32


def test_reponse_identique_compte_connu_ou_non(client, courriels):
    connecter(client, courriels, "connu@exemple.fr")
    client.cookies.clear()
    connu = demander_lien(client, "connu@exemple.fr")
    inconnu = demander_lien(client, "inconnu@exemple.fr")
    assert connu.status_code == inconnu.status_code == 200
    assert connu.text == inconnu.text


def test_adresse_invalide(client):
    assert demander_lien(client, "pas-une-adresse").status_code == 400


def test_cookie_de_session_protege(client, courriels):
    demander_lien(client, "a@exemple.fr")
    reponse = client.get(f"/connexion/{_jeton(courriels)}", follow_redirects=False)
    cookie = reponse.headers["set-cookie"]
    assert cookie.startswith("__Host-session=")
    for attribut in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert attribut.lower() in cookie.lower()


def test_deconnexion_exige_csrf(client, courriels):
    connecter(client, courriels)
    assert client.post("/deconnexion", data={"csrf": "faux"}).status_code == 403


def test_deconnexion(client, courriels):
    csrf = connecter(client, courriels)
    client.post("/deconnexion", data={"csrf": csrf})
    assert "Se déconnecter" not in client.get("/").text


def test_sonde_du_conteneur(client):
    # Chemin lu par le HEALTHCHECK de l'image et par la sonde du conteneur (T080).
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"etat": "ok"}


def test_en_tetes_de_securite(client):
    en_tetes = client.get("/health").headers
    assert "frame-ancestors 'none'" in en_tetes["content-security-policy"]
    assert en_tetes["x-content-type-options"] == "nosniff"


# Anomalie 3 (2026-10-07) : session expirée pendant la navigation ⇒ page d'erreur sans issue.


def test_page_protegee_sans_session_renvoie_vers_la_connexion(client):
    reponse = client.get("/demandes?x=1", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/?motif=session&suite=%2Fdemandes%3Fx%3D1"
    accueil = client.get(reponse.headers["location"]).text
    assert "Votre session a expiré" in accueil
    assert 'name="suite" value="/demandes?x=1"' in accueil


def test_api_sans_session_garde_l_erreur_json(client):
    reponse = client.get("/demandes", headers={"accept": "application/json"})
    assert reponse.status_code == 401 and reponse.json()["erreur"] == "connexion_requise"


def test_retour_a_la_page_demandee_apres_connexion(client, courriels):
    demander_lien(client, "agent@exemple.fr", suite="/demandes")
    reponse = client.get(f"/connexion/{_jeton(courriels)}", follow_redirects=False)
    assert reponse.status_code == 303 and reponse.headers["location"] == "/demandes"
    assert client.get("/demandes").status_code == 200


def test_retour_jamais_vers_un_autre_site(client, courriels):
    from bitumap.api.application import chemin_local

    for piege in ("//exemple.org", "/\\exemple.org", "https://exemple.org", "/connexion/x", "a"):
        assert chemin_local(piege) is None
    demander_lien(client, "agent@exemple.fr", suite="//exemple.org/piege")
    reponse = client.get(f"/connexion/{_jeton(courriels)}", follow_redirects=False)
    assert reponse.headers["location"] == "/"


def test_page_d_erreur_propose_la_page_precedente(client, courriels):
    csrf = connecter(client, courriels)
    assert csrf
    reponse = client.post(
        "/deconnexion", data={"csrf": "perime"}, headers={"referer": "https://testserver/compte"}
    )
    assert reponse.status_code == 403 and 'href="/compte"' in reponse.text
    ailleurs = client.post(
        "/deconnexion", data={"csrf": "perime"}, headers={"referer": "https://exemple.org/x"}
    )
    assert "exemple.org" not in ailleurs.text
