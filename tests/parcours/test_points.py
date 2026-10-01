"""Rapport en vigueur pour un parcours (006 T008) : points au rang estimé, date du rapport."""

from __future__ import annotations

from bitumap.terrain.points import rapport_pour_parcours
from tests.conftest import rapport_courbevoie


def test_rapport_absent(base, s3):
    assert rapport_pour_parcours("92026") is None


def test_points_et_date_du_rapport(base, s3):
    empreinte = rapport_courbevoie()
    rapport = rapport_pour_parcours("92026")
    assert rapport.empreinte == empreinte and rapport.produit_le is not None
    assert len(rapport.points) == 154
    rangs = sorted(p.rang for p in rapport.points.values())
    assert rangs == list(range(1, 155))
    assert {p.groupe for p in rapport.points.values()} == {"P1a", "P1b", "P1c", "P2", "P3"}
