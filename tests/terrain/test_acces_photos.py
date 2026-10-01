"""Accès aux photos (003 R5, FR-015, FR-020, SC-009 ; T023)."""

import pytest

from tests.conftest import connecter, connecter_mainteneur, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import JSON, POINT, deposer, envoyer_photo


@pytest.fixture
def photo(client, courriels, s3):
    rapport_courbevoie()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    releve_id, _ = deposer(client, csrf)
    photo_id, _, confirmation = envoyer_photo(client, csrf, releve_id, images.jpeg_avec_exif())
    assert confirmation.status_code == 201
    return releve_id, photo_id


def test_auteur(client, photo):
    _, photo_id = photo
    reponse = client.get(f"/terrain/photos/{photo_id}")
    assert reponse.status_code == 200 and reponse.headers["content-type"] == "image/jpeg"
    assert reponse.headers["cache-control"] == "private, no-store"
    assert images.metadonnees(reponse.content) == {}


def test_mainteneur(client, courriels, photo, monkeypatch):
    _, photo_id = photo
    client.cookies.clear()
    connecter_mainteneur(client, courriels, monkeypatch)
    assert client.get(f"/terrain/photos/{photo_id}").status_code == 200


def test_autre_compte_ne_voit_aucune_photo(client, courriels, photo):
    releve_id, photo_id = photo
    client.cookies.clear()
    connecter(client, courriels, "autre@exemple.fr")
    assert client.get(f"/terrain/photos/{photo_id}", headers=JSON).status_code == 404
    # fiche de saisie (historique), relevé : seulement le nombre de photos
    fiche = client.get(f"/terrain/92026/{POINT}").text
    assert photo_id not in fiche and "1 photo(s), visibles par leur auteur" in fiche
    releve = client.get(f"/terrain/releves/{releve_id}", headers=JSON).json()
    assert releve["nb_photos"] == 1 and photo_id not in str(releve)


def test_sans_session(client, photo):
    _, photo_id = photo
    client.cookies.clear()
    assert client.get(f"/terrain/photos/{photo_id}", headers=JSON).status_code == 401


def test_identifiant_mal_forme(client, photo):
    assert client.get("/terrain/photos/pas-un-uuid", headers=JSON).status_code == 404
