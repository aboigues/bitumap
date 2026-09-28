"""Connexion par lien e-mail (FR-006, FR-006b, SC-010)."""

from bitumap.db import connexion
from tests.conftest import connecter


def _jeton(courriels):
    return courriels[-1].texte.split("/connexion/", 1)[1].split()[0]


def test_lien_valide_ouvre_une_session(client, courriels):
    csrf = connecter(client, courriels)
    assert csrf
    assert "Se déconnecter" in client.get("/").text


def test_lien_reutilise_refuse(client, courriels):
    client.post("/connexion", data={"email": "a@exemple.fr"})
    jeton = _jeton(courriels)
    assert client.get(f"/connexion/{jeton}", follow_redirects=False).status_code == 303
    client.cookies.clear()
    assert client.get(f"/connexion/{jeton}", follow_redirects=False).status_code == 410


def test_lien_expire_refuse(client, courriels):
    client.post("/connexion", data={"email": "a@exemple.fr"})
    with connexion() as conn:
        conn.execute("UPDATE lien_connexion SET expire_le = now() - interval '1 minute'")
    assert client.get(f"/connexion/{_jeton(courriels)}", follow_redirects=False).status_code == 410


def test_jeton_jamais_stocke_en_clair(client, courriels):
    client.post("/connexion", data={"email": "a@exemple.fr"})
    jeton = _jeton(courriels)
    with connexion() as conn:
        stocke = conn.execute("SELECT empreinte_jeton FROM lien_connexion").fetchone()
    assert jeton.encode() not in bytes(stocke["empreinte_jeton"])
    assert len(bytes(stocke["empreinte_jeton"])) == 32


def test_reponse_identique_compte_connu_ou_non(client, courriels):
    connecter(client, courriels, "connu@exemple.fr")
    client.cookies.clear()
    connu = client.post("/connexion", data={"email": "connu@exemple.fr"})
    inconnu = client.post("/connexion", data={"email": "inconnu@exemple.fr"})
    assert connu.status_code == inconnu.status_code == 200
    assert connu.text == inconnu.text


def test_adresse_invalide(client):
    assert client.post("/connexion", data={"email": "pas-une-adresse"}).status_code == 400


def test_cookie_de_session_protege(client, courriels):
    client.post("/connexion", data={"email": "a@exemple.fr"})
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


def test_en_tetes_de_securite(client):
    en_tetes = client.get("/sante").headers
    assert "frame-ancestors 'none'" in en_tetes["content-security-policy"]
    assert en_tetes["x-content-type-options"] == "nosniff"
