"""Modération par le mainteneur et suppression de compte (003 US5 : FR-016, FR-017, SC-008 ;
T035)."""

import pytest

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import connecter, connecter_mainteneur, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import JSON, POINT, deposer, envoyer_photo


@pytest.fixture
def photo(client, courriels, s3):
    empreinte = rapport_courbevoie()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    releve_id, _ = deposer(client, csrf, observation="à modérer")
    photo_id, _, confirmation = envoyer_photo(client, csrf, releve_id, images.jpeg_avec_exif())
    assert confirmation.status_code == 201
    return csrf, releve_id, photo_id, empreinte


def _versions(cle):
    reponse = stockage._client().list_object_versions(Bucket=reglages().bucket_terrain, Prefix=cle)
    return reponse.get("Versions", []) + reponse.get("DeleteMarkers", [])


def _photo(photo_id):
    with connexion() as conn:
        return conn.execute("SELECT * FROM photo WHERE id = %s", (photo_id,)).fetchone()


def test_page_reservee_au_mainteneur(client, photo):
    assert client.get("/terrain/moderation", headers=JSON).status_code == 404
    assert client.get("/terrain/moderation?q=92026", headers=JSON).status_code == 404


@pytest.mark.parametrize("critere", ["releve", "photo", "commune", "point"])
def test_recherche(client, courriels, photo, monkeypatch, critere):
    _, releve_id, photo_id, _ = photo
    client.cookies.clear()
    connecter_mainteneur(client, courriels, monkeypatch)
    q = {"releve": releve_id, "photo": photo_id, "commune": "92026", "point": POINT}[critere]
    page = client.get(f"/terrain/moderation?q={q}")
    assert page.status_code == 200
    assert releve_id in page.text and photo_id in page.text
    assert "auteur@exemple.fr" in page.text  # adresse complète pour le mainteneur seul (R6)
    assert "private, no-store" in page.headers["cache-control"]


def test_recherche_invalide_ou_vide(client, courriels, photo, monkeypatch):
    client.cookies.clear()
    connecter_mainteneur(client, courriels, monkeypatch)
    assert client.get("/terrain/moderation").status_code == 200
    page = client.get("/terrain/moderation?q=<script>")
    assert page.status_code == 200 and "<script>" not in page.text.split("<main")[1]
    assert "Aucun relevé" in client.get("/terrain/moderation?q=75056").text


def test_retrait_rgpd_d_une_photo(client, courriels, photo, monkeypatch):
    _, releve_id, photo_id, empreinte = photo
    cle = _photo(photo_id)["cle_objet"]
    assert _versions(cle)
    client.cookies.clear()
    csrf = connecter_mainteneur(client, courriels, monkeypatch)
    reponse = client.post(
        f"/terrain/photos/{photo_id}/retrait",
        json={"csrf": csrf, "motif": "demande RGPD n° 12", "rgpd": True},
        headers=JSON,
    )
    assert reponse.status_code == 200
    p = _photo(photo_id)
    # trace conservée sans fichier ; toutes les versions supprimées (SC-008)
    assert p["etat"] == "retiree_mainteneur" and p["motif_retrait"] == "demande RGPD n° 12"
    assert p["retire_le"] is not None and p["retire_par"] is not None
    assert _versions(cle) == []
    assert client.get(f"/terrain/photos/{photo_id}", headers=JSON).status_code == 404
    assert client.get(f"/terrain/releves/{releve_id}", headers=JSON).json()["nb_photos"] == 0
    # ni dans l'export ni dans le rapport
    assert photo_id not in client.get("/terrain/92026/releves.csv").text
    assert '"nb_photos": 0' in client.get(f"/rapports/92026/{empreinte}").text
    # rejoué : sans effet
    rejoue = client.post(
        f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf, "rgpd": True}, headers=JSON
    )
    assert rejoue.status_code == 200


def test_rgpd_reserve_au_mainteneur(client, photo):
    csrf, _, photo_id, _ = photo
    # l'auteur qui demande « rgpd » obtient un retrait simple : fichier conservé
    client.post(
        f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf, "rgpd": True}, headers=JSON
    )
    p = _photo(photo_id)
    assert p["etat"] == "retiree_auteur" and _versions(p["cle_objet"])


def test_retrait_rgpd_d_une_photo_deja_retiree_par_l_auteur(client, courriels, photo, monkeypatch):
    csrf, _, photo_id, _ = photo
    client.post(f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf}, headers=JSON)
    cle = _photo(photo_id)["cle_objet"]
    client.cookies.clear()
    csrf_m = connecter_mainteneur(client, courriels, monkeypatch)
    client.post(
        f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf_m, "rgpd": True}, headers=JSON
    )
    assert _photo(photo_id)["etat"] == "retiree_mainteneur" and _versions(cle) == []


def test_retrait_d_un_releve_par_le_mainteneur(client, courriels, photo, monkeypatch):
    _, releve_id, _, _ = photo
    client.cookies.clear()
    csrf = connecter_mainteneur(client, courriels, monkeypatch)
    reponse = client.post(
        f"/terrain/releves/{releve_id}/retrait",
        json={"csrf": csrf, "rgpd": True},
        headers=JSON,
    )
    assert reponse.status_code == 200
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT motif_retrait, retire_le FROM releve WHERE id = %s", (releve_id,)
        ).fetchone()
    assert ligne["retire_le"] is not None and ligne["motif_retrait"] == "RGPD"
    # la page de modération montre encore la trace
    assert "retiré" in client.get(f"/terrain/moderation?q={releve_id}").text


def test_suppression_du_compte_auteur(client, courriels, photo, monkeypatch):
    csrf, releve_id, photo_id, _ = photo
    client.post(
        "/compte/suppression",
        data={"csrf": csrf, "confirmation": "SUPPRIMER"},
        follow_redirects=False,
    )
    # relevés conservés, auteur anonymisé (FR-017)
    connecter(client, courriels, "lecteur@exemple.fr")
    vue = client.get(f"/terrain/releves/{releve_id}", headers=JSON).json()
    assert vue["auteur"] == "auteur supprimé" and vue["nb_photos"] == 1
    assert client.get(f"/terrain/photos/{photo_id}", headers=JSON).status_code == 404
    # photos d'un auteur supprimé : visibles du seul mainteneur
    client.cookies.clear()
    connecter_mainteneur(client, courriels, monkeypatch)
    assert client.get(f"/terrain/photos/{photo_id}").status_code == 200
    page = client.get(f"/terrain/moderation?q={releve_id}").text
    assert "auteur supprimé" in page


# --- Un nouvel envoi n'annule pas un retrait (LL-014) ------------------------------------


def _quarantaine(photo_id, contenu):
    stockage.ecrire(reglages().bucket_terrain, f"quarantaine/{photo_id}", contenu, "image/jpeg")


def _confirmer(client, csrf, releve_id, photo_id):
    return client.post(
        f"/terrain/releves/{releve_id}/photos/{photo_id}/confirmation",
        json={"csrf": csrf},
        headers=JSON,
    )


@pytest.mark.parametrize("retrait", ["auteur", "rgpd"])
def test_photo_retiree_ne_peut_etre_renvoyee(client, courriels, photo, monkeypatch, retrait):
    csrf, releve_id, photo_id, _ = photo
    if retrait == "auteur":
        client.post(f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf}, headers=JSON)
    else:
        client.cookies.clear()
        csrf_m = connecter_mainteneur(client, courriels, monkeypatch)
        client.post(
            f"/terrain/photos/{photo_id}/retrait",
            json={"csrf": csrf_m, "rgpd": True},
            headers=JSON,
        )
        client.cookies.clear()
        csrf = connecter(client, courriels, "auteur@exemple.fr")
    etat = _photo(photo_id)["etat"]
    # nouveau formulaire refusé
    _, formulaire, _ = envoyer_photo(
        client, csrf, releve_id, images.jpeg_avec_exif(), photo_id=photo_id
    )
    assert formulaire.status_code == 409 and formulaire.json()["erreur"] == "photo_retiree"
    # dépôt direct avec un ancien formulaire : confirmation refusée, original effacé
    _quarantaine(photo_id, images.jpeg_avec_exif())
    confirmation = _confirmer(client, csrf, releve_id, photo_id)
    assert confirmation.status_code == 409
    assert _photo(photo_id)["etat"] == etat
    assert _versions(f"quarantaine/{photo_id}") == []


def test_retrait_pendant_l_envoi(client, courriels, s3, monkeypatch):
    # Photo retirée entre le dépôt en quarantaine et la confirmation : rien ne reste.
    rapport_courbevoie()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    releve_id, _ = deposer(client, csrf)
    photo_id = "7d0e8f3a-2b1c-4d5e-8f90-a1b2c3d4e5f6"
    formulaire = client.post(
        f"/terrain/releves/{releve_id}/photos/{photo_id}/formulaire",
        json={"csrf": csrf, "octets": 1000, "type": "image/jpeg"},
        headers=JSON,
    )
    assert formulaire.status_code == 200
    _quarantaine(photo_id, images.jpeg_avec_exif())
    client.cookies.clear()
    csrf_m = connecter_mainteneur(client, courriels, monkeypatch)
    client.post(
        f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf_m, "rgpd": True}, headers=JSON
    )
    client.cookies.clear()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    assert _confirmer(client, csrf, releve_id, photo_id).status_code == 409
    assert _photo(photo_id)["etat"] == "retiree_mainteneur"
    assert _versions(f"quarantaine/{photo_id}") == []
    assert _versions("communes/92026/points/") == []


def test_depot_rejoue_apres_succes(client, photo):
    # Réponse perdue : le téléphone redépose et reconfirme ; idempotent, original effacé.
    csrf, releve_id, photo_id, _ = photo
    _quarantaine(photo_id, images.jpeg_avec_exif())
    assert _confirmer(client, csrf, releve_id, photo_id).status_code == 201
    assert _photo(photo_id)["etat"] == "visible"
    assert _versions(f"quarantaine/{photo_id}") == []
