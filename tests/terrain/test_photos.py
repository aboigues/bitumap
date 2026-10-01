"""Photos des relevés (003 R4, R8 ; FR-003, FR-018, FR-019 ; SC-006 ; T014)."""

import base64
import json

import pytest

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import EMAIL_MAINTENEUR, connecter, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import JSON, deposer, envoyer_photo


@pytest.fixture
def releve(client, courriels, s3):
    rapport_courbevoie()
    csrf = connecter(client, courriels)
    releve_id, reponse = deposer(client, csrf)
    assert reponse.status_code == 201
    return csrf, releve_id


def _photo(photo_id):
    with connexion() as conn:
        return conn.execute("SELECT * FROM photo WHERE id = %s", (photo_id,)).fetchone()


def test_formulaire_signe_borne(client, releve):
    csrf, releve_id = releve
    _, formulaire, _ = envoyer_photo(client, csrf, releve_id, images.jpeg_avec_exif())
    corps = formulaire.json()
    politique = json.loads(base64.b64decode(corps["champs"]["policy"]))
    conditions = politique["conditions"]
    assert ["content-length-range", 1, reglages().photo_max_octets] in conditions
    assert {"Content-Type": "image/jpeg"} in conditions
    assert corps["champs"]["key"].startswith("quarantaine/")


def test_photo_reencodee_sans_metadonnees(client, releve, s3):
    csrf, releve_id = releve
    photo_id, _, confirmation = envoyer_photo(client, csrf, releve_id, images.jpeg_avec_exif())
    assert confirmation.status_code == 201
    p = _photo(photo_id)
    assert p["etat"] == "visible" and p["lon"] == pytest.approx(2.2606)
    contenu = stockage.lire(reglages().bucket_terrain, p["cle_objet"])
    assert images.metadonnees(contenu) == {}  # SC-006 : ni appareil, ni auteur, ni GPS
    assert stockage.lire(reglages().bucket_terrain, f"quarantaine/{photo_id}") is None


def _versions_quarantaine(photo_id):
    reponse = stockage._client().list_object_versions(
        Bucket=reglages().bucket_terrain, Prefix=f"quarantaine/{photo_id}"
    )
    return reponse.get("Versions", []) + reponse.get("DeleteMarkers", [])


def test_original_non_conserve_par_le_versionnement(client, releve):
    # Bucket versionné : une simple suppression garderait l'original (EXIF, GPS) en version
    # non courante, récupérable (LL-013).
    csrf, releve_id = releve
    photo_id, _, _ = envoyer_photo(client, csrf, releve_id, images.jpeg_avec_exif())
    assert _versions_quarantaine(photo_id) == []
    rejete, _, _ = envoyer_photo(client, csrf, releve_id, images.faux_jpeg())
    assert _versions_quarantaine(rejete) == []


def test_png_accepte(client, releve):
    csrf, releve_id = releve
    _, _, confirmation = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    assert confirmation.status_code == 201


def test_contenu_non_image(client, releve):
    csrf, releve_id = releve
    photo_id, _, confirmation = envoyer_photo(client, csrf, releve_id, images.faux_jpeg())
    assert confirmation.status_code == 400 and confirmation.json()["erreur"] == "image_invalide"
    assert _photo(photo_id) is None
    assert stockage.lire(reglages().bucket_terrain, f"quarantaine/{photo_id}") is None


def test_type_et_taille(client, releve):
    csrf, releve_id = releve
    _, formulaire, _ = envoyer_photo(client, csrf, releve_id, b"GIF89a", "image/gif")
    assert formulaire.status_code == 400
    _, trop_lourd, _ = envoyer_photo(
        client, csrf, releve_id, images.trop_lourd(reglages().photo_max_octets + 1)
    )
    assert trop_lourd.status_code == 413 and trop_lourd.json()["erreur"] == "photo_trop_lourde"


def test_cinq_photos_au_plus(client, releve):
    csrf, releve_id = releve
    for _ in range(5):
        _, _, confirmation = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
        assert confirmation.status_code == 201
    _, formulaire, _ = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    assert formulaire.status_code == 409 and formulaire.json()["erreur"] == "trop_de_photos"


def test_confirmation_rejouee(client, releve):
    csrf, releve_id = releve
    photo_id, _, _ = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    rejouee = client.post(
        f"/terrain/releves/{releve_id}/photos/{photo_id}/confirmation",
        json={"csrf": csrf},
        headers=JSON,
    )
    assert rejouee.status_code == 201


def test_pas_l_auteur(client, courriels, releve):
    _, releve_id = releve
    client.cookies.clear()
    autre = connecter(client, courriels, "autre@exemple.fr")
    _, formulaire, _ = envoyer_photo(client, autre, releve_id, images.png(), "image/png")
    assert formulaire.status_code == 403 and formulaire.json()["erreur"] == "pas_auteur"


def test_quota_photos(client, releve, monkeypatch):
    csrf, releve_id = releve
    monkeypatch.setattr(reglages(), "quota_photos_compte_jour", 1)
    assert envoyer_photo(client, csrf, releve_id, images.png(), "image/png")[2].status_code == 201
    _, formulaire, _ = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    assert formulaire.status_code == 429 and formulaire.json()["erreur"] == "quota_photos"


def test_stockage_plein_et_alerte_unique(client, courriels, releve, monkeypatch):
    csrf, releve_id = releve
    monkeypatch.setattr(reglages(), "email_mainteneur", EMAIL_MAINTENEUR)
    monkeypatch.setattr(reglages(), "photos_max_go", 0.0)
    for _ in range(2):
        _, formulaire, _ = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
        assert formulaire.status_code == 507 and formulaire.json()["erreur"] == "stockage_plein"
    alertes = [c for c in courriels if "stockage des photos" in c.sujet]
    assert len(alertes) == 1
