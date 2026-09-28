"""Fixtures partagées : base PostgreSQL de test, S3 simulé, client HTTP.

La base est celle de ``compose.yaml`` en local (port 55432) ou le service PostgreSQL de la CI
(``BITUMAP_DB_URL_TEST``). Le schéma est recréé à chaque session de tests.
"""

from __future__ import annotations

import os

import pytest

URL_TEST = os.environ.get(
    "BITUMAP_DB_URL_TEST", "postgresql://bitumap:bitumap-local@127.0.0.1:55432/bitumap"
)
os.environ["BITUMAP_DB_URL"] = URL_TEST
os.environ["BITUMAP_COURRIEL_MODE"] = "console"
os.environ["BITUMAP_URL_PUBLIQUE"] = "https://testserver"
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

TABLES = (
    "demandeur_demande, demande, lot, session, lien_connexion, compte, preuve_antibot,"
    " compteur_quota, cout_ia_jour, source_version, alerte_envoyee, ia_cache_point"
)


@pytest.fixture(scope="session")
def schema():
    import psycopg

    from bitumap.config import reglages
    from bitumap.db.migrer import migrer

    reglages.cache_clear()
    try:
        with psycopg.connect(URL_TEST, connect_timeout=3) as conn:
            conn.execute("DROP SCHEMA public CASCADE")
            conn.execute("CREATE SCHEMA public")
    except psycopg.OperationalError:
        pytest.skip("base PostgreSQL de test indisponible (docker compose up -d db)")
    migrer(URL_TEST)
    yield
    from bitumap.db import fermer_pool

    fermer_pool()


@pytest.fixture
def base(schema):
    """Base vide pour chaque test."""
    from bitumap.db import connexion

    with connexion() as conn:
        conn.execute(f"TRUNCATE {TABLES} CASCADE")
    yield


@pytest.fixture
def courriels():
    from bitumap import courriel

    courriel.ENVOYES.clear()
    yield courriel.ENVOYES
    courriel.ENVOYES.clear()


@pytest.fixture
def client(base, courriels):
    from fastapi.testclient import TestClient

    from bitumap.api import creer_application

    with TestClient(creer_application(), base_url="https://testserver") as c:
        yield c


def connecter(client, courriels, email="agent@exemple.fr"):
    """Parcours complet de connexion par lien ; renvoie le jeton CSRF de la session."""
    client.post("/connexion", data={"email": email})
    lien = courriels[-1].texte.split("https://testserver", 1)[1].split()[0]
    reponse = client.get(lien, follow_redirects=False)
    assert reponse.status_code == 303
    page = client.get("/").text
    return page.split('name="csrf" value="', 1)[1].split('"', 1)[0]


@pytest.fixture
def s3(monkeypatch):
    """Stockage objet simulé (moto) avec les buckets du service."""
    from moto import mock_aws

    from bitumap import stockage
    from bitumap.config import reglages

    monkeypatch.setattr(reglages(), "s3_endpoint", None)
    monkeypatch.setattr(reglages(), "s3_region", "eu-west-3")
    stockage.reinitialiser_client()
    with mock_aws():
        client = stockage._client()
        for bucket in (reglages().bucket_rapports, reglages().bucket_cache):
            client.create_bucket(
                Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-3"}
            )
        yield client
    stockage.reinitialiser_client()


@pytest.fixture
def territoire(monkeypatch):
    """API Géo simulée : 92400 → Courbevoie ; 95000 → 4 communes."""
    from bitumap.api import demandes
    from bitumap.territoire import Commune, ErreurTerritoire

    communes = {
        "92400": [Commune("92026", "Courbevoie", "92")],
        "95000": [
            Commune("95074", "Boisemont", "95"),
            Commune("95127", "Cergy", "95"),
            Commune("95450", "Neuville-sur-Oise", "95"),
            Commune("95500", "Pontoise", "95"),
        ],
    }
    par_insee = {c.insee: c for liste in communes.values() for c in liste}

    def du_code_postal(code):
        from bitumap.territoire import valider_format

        valider_format(code)
        if code not in communes:
            raise ErreurTerritoire("code_inexistant", "Ce code postal n'existe pas.")
        return communes[code]

    def par_code_insee(insee):
        if insee not in par_insee:
            raise ErreurTerritoire("commune_invalide", "Commune inconnue.")
        return par_insee[insee]

    monkeypatch.setattr(demandes, "communes_du_code_postal", du_code_postal)
    monkeypatch.setattr(demandes, "commune_par_insee", par_code_insee)
    return par_insee
