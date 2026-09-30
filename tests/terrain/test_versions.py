"""Corriger ou retirer son relevé (003 US3 : FR-011, FR-012, SC-005, R11, R12 ; T029)."""

import pytest

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import JSON, POINT, deposer, envoyer_photo


@pytest.fixture
def releve(client, courriels, s3):
    empreinte = rapport_courbevoie()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    releve_id, reponse = deposer(client, csrf, niveau="leger", observation="première saisie")
    assert reponse.status_code == 201
    return csrf, releve_id, empreinte


def _corriger(client, csrf, releve_id, **champs):
    corps = {"niveau": "marque", "csrf": csrf} | champs
    return client.post(f"/terrain/releves/{releve_id}/versions", json=corps, headers=JSON)


def _versions(releve_id):
    with connexion() as conn:
        return conn.execute(
            "SELECT version, niveau, observation FROM releve_version WHERE releve_id = %s"
            " ORDER BY version",
            (releve_id,),
        ).fetchall()


def test_correction_ajoute_une_version(client, releve):
    csrf, releve_id, _ = releve
    reponse = _corriger(client, csrf, releve_id, profondeur_mm=15, instrument="règle et cale")
    assert reponse.status_code == 201 and reponse.json()["version"] == 2
    # rien n'est modifié en place (SC-005)
    assert [(v["version"], v["niveau"]) for v in _versions(releve_id)] == [
        (1, "leger"),
        (2, "marque"),
    ]
    assert _versions(releve_id)[0]["observation"] == "première saisie"
    vue = client.get(f"/terrain/releves/{releve_id}", headers=JSON).json()
    assert vue["niveau"] == "marque" and vue["version"] == 2
    assert [v["version"] for v in vue["versions"]] == [2, 1]
    fiche = client.get(f"/terrain/92026/{POINT}").text
    assert "version 2" in fiche


def test_correction_rejouee_sans_doublon(client, releve):
    # la correction passe par la file hors réseau : un réenvoi ne crée pas de version
    csrf, releve_id, _ = releve
    assert _corriger(client, csrf, releve_id, version=2).status_code == 201
    rejouee = _corriger(client, csrf, releve_id, version=2)
    assert rejouee.status_code == 200 and rejouee.json()["deja_enregistre"] is True
    assert len(_versions(releve_id)) == 2
    conflit = _corriger(client, csrf, releve_id, version=2, niveau="grave")
    assert conflit.status_code == 409 and conflit.json()["erreur"] == "version_prise"
    saut = _corriger(client, csrf, releve_id, version=5)
    assert saut.status_code == 409 and saut.json()["erreur"] == "version_prise"


def test_correction_coherence(client, releve):
    csrf, releve_id, _ = releve
    reponse = _corriger(client, csrf, releve_id, profondeur_mm=30, instrument="jauge")
    assert reponse.status_code == 200 and reponse.json()["niveau_suggere"] == "grave"
    assert len(_versions(releve_id)) == 1
    confirme = _corriger(
        client,
        csrf,
        releve_id,
        profondeur_mm=30,
        instrument="jauge",
        confirme_malgre_incoherence=True,
    )
    assert confirme.status_code == 201


def test_correction_par_un_autre_compte(client, courriels, releve):
    _, releve_id, _ = releve
    client.cookies.clear()
    autre = connecter(client, courriels, "autre@exemple.fr")
    reponse = _corriger(client, autre, releve_id)
    assert reponse.status_code == 403 and reponse.json()["erreur"] == "pas_auteur"
    retrait = client.post(
        f"/terrain/releves/{releve_id}/retrait", json={"csrf": autre}, headers=JSON
    )
    assert retrait.status_code == 403


def test_correction_invalide_ou_sans_csrf(client, releve):
    csrf, releve_id, _ = releve
    assert _corriger(client, csrf, releve_id, niveau="enorme").status_code == 400
    assert _corriger(client, "faux", releve_id).status_code == 403
    inconnu = "00000000-0000-4000-8000-000000000000"
    assert _corriger(client, csrf, inconnu).status_code == 404


def test_retrait_du_releve_par_l_auteur(client, releve):
    csrf, releve_id, empreinte = releve
    reponse = client.post(
        f"/terrain/releves/{releve_id}/retrait",
        json={"csrf": csrf, "motif": "erreur de point"},
        headers=JSON,
    )
    assert reponse.status_code == 200
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT r.retire_le, r.retire_par, r.motif_retrait, r.compte_id FROM releve r"
            " WHERE id = %s",
            (releve_id,),
        ).fetchone()
    assert ligne["retire_le"] is not None and ligne["retire_par"] == ligne["compte_id"]
    assert ligne["motif_retrait"] == "erreur de point"
    # masqué partout : fiche, relevé, rapport
    assert client.get(f"/terrain/releves/{releve_id}", headers=JSON).status_code == 404
    assert "première saisie" not in client.get(f"/terrain/92026/{POINT}").text
    assert '"releves">{}' in client.get(f"/rapports/92026/{empreinte}").text
    # retrait rejoué : sans effet
    rejoue = client.post(f"/terrain/releves/{releve_id}/retrait", json={"csrf": csrf}, headers=JSON)
    assert rejoue.status_code == 200
    assert _corriger(client, csrf, releve_id).status_code == 404


def test_retrait_d_une_photo_par_l_auteur(client, releve):
    csrf, releve_id, _ = releve
    photo_id, _, confirmation = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    assert confirmation.status_code == 201
    reponse = client.post(
        f"/terrain/photos/{photo_id}/retrait", json={"csrf": csrf, "motif": "floue"}, headers=JSON
    )
    assert reponse.status_code == 200
    with connexion() as conn:
        photo = conn.execute("SELECT * FROM photo WHERE id = %s", (photo_id,)).fetchone()
    assert photo["etat"] == "retiree_auteur" and photo["retire_le"] is not None
    assert photo["motif_retrait"] == "floue"
    # fichier conservé (historique, R12), mais plus servi ni compté
    assert stockage.lire(reglages().bucket_terrain, photo["cle_objet"]) is not None
    assert client.get(f"/terrain/photos/{photo_id}", headers=JSON).status_code == 404
    assert client.get(f"/terrain/releves/{releve_id}", headers=JSON).json()["nb_photos"] == 0
    # une place libérée : une nouvelle photo est acceptée
    assert envoyer_photo(client, csrf, releve_id, images.png(), "image/png")[2].status_code == 201


def test_retrait_d_une_photo_par_un_autre_compte(client, courriels, releve):
    csrf, releve_id, _ = releve
    photo_id, _, _ = envoyer_photo(client, csrf, releve_id, images.png(), "image/png")
    client.cookies.clear()
    autre = connecter(client, courriels, "autre@exemple.fr")
    reponse = client.post(f"/terrain/photos/{photo_id}/retrait", json={"csrf": autre}, headers=JSON)
    assert reponse.status_code == 404  # aucune fuite d'existence (R5)
    with connexion() as conn:
        etat = conn.execute("SELECT etat FROM photo WHERE id = %s", (photo_id,)).fetchone()
    assert etat["etat"] == "visible"
