"""Pseudonyme d'auteur (003 R6, T008)."""

import re

from bitumap.terrain.pseudonyme import AUTEUR_SUPPRIME, VOUS, pseudonyme

A = "5b0a4d9e-0000-4000-8000-000000000001"
B = "5b0a4d9e-0000-4000-8000-000000000002"


def test_stable_et_sans_adresse():
    p = pseudonyme(A, "j.dupont@ville-courbevoie.fr")
    assert p == pseudonyme(A, "j.dupont@ville-courbevoie.fr")
    assert re.fullmatch(r"agent [0-9A-F]{4} · ville-courbevoie\.fr", p)
    assert "dupont" not in p


def test_deux_comptes_distincts():
    assert pseudonyme(A, "a@exemple.fr") != pseudonyme(B, "b@exemple.fr")


def test_vous_et_auteur_supprime():
    assert pseudonyme(A, "a@exemple.fr", lecteur_id=A) == VOUS
    assert pseudonyme(None, None) == AUTEUR_SUPPRIME
