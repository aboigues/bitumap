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
