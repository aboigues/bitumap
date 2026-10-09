"""Icône du site (issue #56) : /favicon.ico, icône SVG des pages, fichiers à jour."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATIQUE = REPO / "src" / "bitumap" / "api" / "statique"


def test_favicon_a_la_racine(client):
    reponse = client.get("/favicon.ico")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "image/x-icon"
    assert reponse.content[:4] == b"\x00\x00\x01\x00"  # en-tête d'un fichier ICO
    assert reponse.headers["cache-control"] == "public, max-age=86400"


def test_icone_annoncee_par_les_pages(client):
    page = client.get("/").text
    assert '<link rel="icon" href="/favicon.ico" sizes="48x48">' in page
    assert '<link rel="icon" href="/statique/favicon.svg" type="image/svg+xml">' in page
    svg = client.get("/statique/favicon.svg")
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")


def test_fichiers_produits_par_le_generateur():
    """Les fichiers versionnés sont ceux que produit tools/favicon.py (pas de dérive)."""
    spec = importlib.util.spec_from_file_location("favicon", REPO / "tools" / "favicon.py")
    generateur = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generateur)
    assert (STATIQUE / "favicon.svg").read_text() == generateur.SVG
