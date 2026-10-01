"""Téléchargements des sources (004 T044) : URL tierces vérifiées, taille bornée."""

from __future__ import annotations

import httpx
import pytest
import respx

from bitumap.sources.base import SourceIndisponible, telecharger, verifier_url

HOTES = ("static.data.gouv.fr",)


@pytest.mark.parametrize(
    "url",
    [
        "http://static.data.gouv.fr/a.zip",  # pas HTTPS
        "https://static.data.gouv.fr.exemple.test/a.zip",  # autre hôte
        "file:///etc/passwd",
        "/vsicurl/https://static.data.gouv.fr/a.zip",
        "https://169.254.42.42/latest",
    ],
)
def test_url_refusee(url):
    with pytest.raises(SourceIndisponible, match="URL"):
        verifier_url("source", url, HOTES)


def test_url_acceptee():
    url = "https://static.data.gouv.fr/resources/a.zip"
    assert verifier_url("source", url, HOTES) == url


@respx.mock
def test_taille_annoncee_trop_grande():
    respx.get("https://static.data.gouv.fr/a").mock(
        return_value=httpx.Response(200, headers={"content-length": "2000"}, content=b"x" * 2000)
    )
    with httpx.Client() as client, pytest.raises(SourceIndisponible, match="trop lourd"):
        telecharger(client, "source", "https://static.data.gouv.fr/a", 1000)


@respx.mock
def test_taille_reelle_trop_grande_sans_annonce():
    def flux(requete):
        return httpx.Response(200, stream=httpx.ByteStream(b"x" * 2000))

    respx.get("https://static.data.gouv.fr/a").mock(side_effect=flux)
    with httpx.Client() as client, pytest.raises(SourceIndisponible, match="trop lourd"):
        telecharger(client, "source", "https://static.data.gouv.fr/a", 1000)


@respx.mock
def test_fichier_dans_la_limite_et_nouvel_essai(monkeypatch):
    monkeypatch.setattr("bitumap.sources.base.time.sleep", lambda s: None)
    route = respx.get("https://static.data.gouv.fr/a").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, content=b"contenu")]
    )
    with httpx.Client() as client:
        assert telecharger(client, "source", "https://static.data.gouv.fr/a", 1000) == b"contenu"
    assert route.call_count == 2
