"""Export des relevés d'une commune (003 US4 : FR-013, FR-014, SC-007 ; T032)."""

import csv
import io
import json

import pytest

from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.score.methode import LIBELLES_GROUPES
from bitumap.terrain.points import points_en_vigueur
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import JSON, POINT, deposer, envoyer_photo

AUTRE_POINT = "A8083"


@pytest.fixture
def releves(client, courriels, s3):
    rapport_courbevoie()
    csrf = connecter(client, courriels, "auteur@exemple.fr")
    mien, _ = deposer(
        client,
        csrf,
        niveau="marque",
        profondeur_mm=15,
        instrument="règle et cale",
        annee_refection=2019,
        source_refection="services_techniques",
        observation='=HYPERLINK("http://exemple.invalid")',
    )
    photo_id, _, _ = envoyer_photo(client, csrf, mien, images.png(), "image/png")
    client.cookies.clear()
    csrf_b = connecter(client, courriels, "collegue@exemple.fr")
    sien, _ = deposer(
        client,
        csrf_b,
        point_id=AUTRE_POINT,
        niveau="absent",
        annee_refection=2022,
        source_refection="estimee_agent",
    )
    envoyer_photo(client, csrf_b, sien, images.png(), "image/png")
    retire, _ = deposer(client, csrf_b, niveau="grave")
    client.post(f"/terrain/releves/{retire}/retrait", json={"csrf": csrf_b}, headers=JSON)
    client.cookies.clear()
    connecter(client, courriels, "auteur@exemple.fr")
    return mien, sien, retire, photo_id


def _csv(client):
    reponse = client.get("/terrain/92026/releves.csv")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/csv")
    assert "attachment" in reponse.headers["content-disposition"]
    assert reponse.content.startswith(b"\xef\xbb\xbf")  # BOM : accents lus par le tableur
    return list(csv.DictReader(io.StringIO(reponse.content.decode("utf-8-sig")), delimiter=";"))


def test_csv(client, releves):
    mien, sien, _retire, photo_id = releves
    lignes = {ligne["releve"]: ligne for ligne in _csv(client)}
    assert set(lignes) == {mien, sien}  # relevé retiré absent
    a = lignes[mien]
    assert a["point"] == POINT and a["niveau_constate"] == "marqué"
    assert a["niveau_estime"] and a["profondeur_mm"] == "15" and a["instrument"] == "règle et cale"
    assert a["annee_refection"] == "2019" and a["source_refection"] == "services techniques"
    assert a["auteur"] == "vous" and a["nb_photos"] == "1"
    assert a["photos"] == f"{reglages().url_publique.rstrip('/')}/terrain/photos/{photo_id}"
    assert float(a["lon"]) == pytest.approx(2.2606, abs=0.01)
    # texte libre neutralisé : aucune formule exécutée à l'ouverture (injection CSV)
    assert a["observation"].startswith("'=")
    b = lignes[sien]
    assert b["auteur"].startswith("agent ") and b["nb_photos"] == "1" and b["photos"] == ""


def test_niveau_estime_du_rapport_en_vigueur(client, releves):
    mien, *_ = releves
    with connexion() as conn:  # le niveau copié à la saisie n'est pas celui exporté
        conn.execute("UPDATE releve SET niveau_estime = 'P3' WHERE id = %s", (mien,))
    ligne = next(li for li in _csv(client) if li["releve"] == mien)
    _, points = points_en_vigueur("92026")
    assert ligne["niveau_estime"] == LIBELLES_GROUPES[points[POINT].groupe]
    assert points[POINT].groupe != "P3"


def test_geojson(client, releves):
    mien, sien, _, photo_id = releves
    reponse = client.get("/terrain/92026/releves.geojson")
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["type"] == "FeatureCollection" and len(donnees["features"]) == 2
    entites = {f["properties"]["releve"]: f for f in donnees["features"]}
    a = entites[mien]
    assert a["geometry"]["type"] == "Point"
    lon, lat = a["geometry"]["coordinates"]
    assert 2.2 < lon < 2.3 and 48.8 < lat < 48.95  # WGS 84 (lon, lat)
    assert a["properties"]["niveau_constate"] == "marqué"
    assert a["properties"]["photos"] == [
        f"{reglages().url_publique.rstrip('/')}/terrain/photos/{photo_id}"
    ]
    assert entites[sien]["properties"]["photos"] == []


def test_echantillon_refection(client, releves):
    reponse = client.get("/terrain/92026/echantillon_refection.json")
    assert reponse.status_code == 200
    points = reponse.json()["points"]
    # seulement les sources fiables (constatée, services techniques)
    assert [p["id"] for p in points] == [POINT]
    p = points[0]
    assert set(p) >= {"id", "nom", "lon", "lat", "refection_annee", "source"}
    assert p["refection_annee"] == 2019 and p["source"] == "services_techniques"
    # lisible par l'évaluation de l'IA (002 T072), sans appel au modèle
    echantillon = json.loads(reponse.content)["points"]
    assert all(int(q["refection_annee"]) and q["lon"] and q["lat"] for q in echantillon)


def test_export_sans_session_ou_commune_invalide(client, releves):
    assert client.get("/terrain/9202X/releves.csv").status_code == 404
    client.cookies.clear()
    assert client.get("/terrain/92026/releves.csv", headers=JSON).status_code == 401


def test_liens_d_export_sur_la_page(client, releves):
    page = client.get("/terrain/92026").text
    for chemin in ("releves.csv", "releves.geojson", "echantillon_refection.json"):
        assert f"/terrain/92026/{chemin}" in page
