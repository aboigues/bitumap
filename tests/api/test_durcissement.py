"""Durcissement relevé par l'audit de sécurité local du 2026-09-30."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path


def test_security_txt(client):
    reponse = client.get("/.well-known/security.txt")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/plain")
    texte = reponse.text
    assert "Contact: https://github.com/aboigues/bitumap/security/advisories/new" in texte
    assert "Canonical: " in texte and texte.endswith("/.well-known/security.txt\n")
    # RFC 9116 : « Expires » obligatoire, à moins d'un an
    expire = re.search(r"^Expires: (\S+)$", texte, re.M).group(1)
    echeance = datetime.strptime(expire, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert datetime.now(UTC) < echeance < datetime.now(UTC) + timedelta(days=365)


def test_image_api_sans_en_tete_server():
    # uvicorn envoie « server: uvicorn » par défaut : empreinte inutile de la pile.
    dockerfile = Path(__file__).parents[2] / "docker" / "api.Dockerfile"
    point_entree = next(
        ligne for ligne in dockerfile.read_text().splitlines() if ligne.startswith("ENTRYPOINT")
    )
    assert '"--no-server-header"' in point_entree


def test_le_job_demarre_sans_les_secrets_de_l_api(monkeypatch):
    # Le job ne reçoit ni la clé ALTCHA ni le sel (moindre privilège, infra/tofu/job.tf) :
    # sa configuration doit se charger sans eux.
    from bitumap.config import reglages

    monkeypatch.delenv("BITUMAP_ALTCHA_HMAC")
    monkeypatch.delenv("BITUMAP_SEL_ORIGINE")
    monkeypatch.chdir(Path(__file__).parent)  # aucun .env local
    reglages.cache_clear()
    try:
        assert reglages().altcha_hmac is None and reglages().sel_origine is None
    finally:
        reglages.cache_clear()


def test_l_api_refuse_de_demarrer_sans_ses_secrets(monkeypatch):
    import pytest
    from fastapi.testclient import TestClient

    from bitumap.api import creer_application
    from bitumap.config import reglages

    monkeypatch.delenv("BITUMAP_SEL_ORIGINE")
    monkeypatch.chdir(Path(__file__).parent)
    reglages.cache_clear()
    try:
        with (
            pytest.raises(RuntimeError, match="BITUMAP_SEL_ORIGINE"),
            TestClient(creer_application()),
        ):
            pass
    finally:
        reglages.cache_clear()


def test_l_api_demarre_avec_ses_secrets():
    from fastapi.testclient import TestClient

    from bitumap.api import creer_application

    with TestClient(creer_application()) as client:
        assert client.get("/health").json() == {"etat": "ok"}
