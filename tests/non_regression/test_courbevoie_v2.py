"""Courbevoie figée en méthode 2.0 (004), sans réseau : ensoleillement LiDAR HD (US1).

La non-régression face au prototype reste celle de la 1.2 (``test_courbevoie.py``, inchangé) ;
pour la 2.0, chaque changement de niveau devra porter sa raison (US4, T040).
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from bitumap.calcul import calculer_commune
from bitumap.config import reglages
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "courbevoie"


@cache
def _calcul(methode: str):
    ancienne = reglages().methode
    reglages().methode = methode
    try:
        return calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")
    finally:
        reglages().methode = ancienne


def _soleil(resultat):
    return {p.id: p.facteur("ensoleillement") for p in resultat.points}


def test_ensoleillement_lidar_pour_tous_les_points():
    soleil = _soleil(_calcul("2.0"))
    assert Counter(f.details["source"] for f in soleil.values()) == {"lidar_hd": len(soleil)}
    assert all(0 <= f.valeur <= 12 for f in soleil.values())
    assert all(f.details["millesime_lidar"] for f in soleil.values())


def test_issue_18_sous_le_pont():
    resultat = _calcul("2.0")
    p = next(p for p in resultat.points if p.id == "A27418")  # Verdun - Rue Latérale
    f = p.facteur("ensoleillement")
    assert f.valeur <= 1.5 and f.details["cause_ombre"] == "ouvrage"
    assert p.groupe not in ("P1a", "P1b", "P1c")


def test_causes_d_ombre_variees():
    causes = Counter(f.details["cause_ombre"] for f in _soleil(_calcul("2.0")).values())
    assert causes["batiment"] and causes["arbre"] and causes["ouvrage"]


def test_deterministe():
    premier = [(p.id, p.facteur("ensoleillement").valeur, p.rang) for p in _calcul("2.0").points]
    reglages().methode = "2.0"
    try:
        second = calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")
    finally:
        reglages().methode = "1.2"
    assert premier == [(p.id, p.facteur("ensoleillement").valeur, p.rang) for p in second.points]


def test_la_1_2_ignore_les_hauteurs():
    soleil = _soleil(_calcul("1.2"))
    assert all(not f.details for f in soleil.values())
    assert not any("LiDAR" in p.nom for p in _calcul("1.2").provenances)
    assert any("LiDAR" in p.nom for p in _calcul("2.0").provenances)


@pytest.mark.parametrize("ident", ["A23742"])  # « Paix - Verdun », orniérage constaté en 2026
def test_point_de_reference_reste_prioritaire(ident):
    p = next(p for p in _calcul("2.0").points if p.id == ident)
    assert p.groupe in ("P1a", "P1b", "P1c")


def test_poids_lourds_sur_les_comptages_publies():
    """004 US3 (test indépendant) : départementale comptée à fort trafic > voie comptée
    faible ; voie communale ⇒ ×1,0 « non évalué »."""
    resultat = _calcul("2.0")
    pl = {p.id: (p, p.facteur("poids_lourds")) for p in resultat.points}
    assert all(f is not None for _, f in pl.values())
    quai = pl["A25835"][1]  # quai du Président Paul Doumer, RD7
    assert quai.details["troncon"].startswith("RD7") and quai.effet > 1.2
    gaultier = pl["A420570"][1]  # rue Gaultier, RD12 : moins de poids lourds que de bus
    assert gaultier.statut == "evalue" and gaultier.effet == 1.0
    communales = [f for p, f in pl.values() if p.route.classement.startswith("communale")]
    assert communales and all((f.effet, f.statut) == (1.0, "non_evalue") for f in communales)
    assert any("Hauts-de-Seine" in p.nom for p in resultat.provenances)


def test_couverture_poids_lourds_dans_la_synthese():
    from bitumap.rapport.rendu import _synthese

    resultat = _calcul("2.0")
    evalues = sum(p.facteur("poids_lourds").statut == "evalue" for p in resultat.points)
    assert _synthese(resultat)["couverture_poids_lourds"] == round(
        100 * evalues / len(resultat.points)
    )
    assert "couverture_poids_lourds" not in _synthese(_calcul("1.2"))


def test_la_1_2_ignore_les_comptages():
    resultat = _calcul("1.2")
    assert all(p.facteur("poids_lourds") is None for p in resultat.points)
    assert not any("poids lourds" in p.nom for p in resultat.provenances)
