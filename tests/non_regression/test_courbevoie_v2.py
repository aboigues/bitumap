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


def test_chaleur_candidats_affiches_sans_effet():
    """004 US2 : quatre indicateurs par point, non retenus (effet 1,0) ; été de référence."""
    from bitumap.facteurs import chaleur

    resultat = _calcul("2.0")
    assert resultat.ete_reference == {
        "annee": 2026,
        "station": "75114001",
        "station_nom": "PARIS-MONTSOURIS",
        "jours_mesures": 92,
        "jours_forte_chaleur": 39,
        "jours_tres_forte_chaleur": 20,
        "maximum_c": 40.6,
        "temperature_ete": 2026,
    }
    for p in resultat.points:
        assert p.facteur("chaleur") is None
        facteurs = [p.facteur(nom) for nom in chaleur.CANDIDATS]
        assert all(f is not None and f.effet == 1.0 for f in facteurs)
    temperatures = [p.facteur(chaleur.TEMPERATURE).valeur for p in resultat.points]
    assert None not in temperatures and max(temperatures) - min(temperatures) > 5
    hors_ue = [p for p in resultat.provenances if p.hors_ue]
    assert [p.nom.split(",")[0] for p in hors_ue] == ["USGS Landsat Collection 2 niveau 2"]
    assert _calcul("1.2").ete_reference is None


def _ecart_deciles(effets: list[float]) -> float:
    """SC-003 : écart d'effet entre les 10 % de points les plus exposés et les 10 % les
    moins exposés."""
    tries = sorted(effets)
    k = max(1, round(len(tries) * 0.1))
    return (sum(tries[-k:]) / k) / (sum(tries[:k]) / k) - 1


def test_sc_003_mesure_par_candidat():
    """T029 : mesure consignée (research R4), pas encore bloquante. Les bornes de chaque
    indicateur (×0,92 à ×1,08, celles de l'aléa) plafonnent l'écart à 17,4 % : le seuil de
    SC-003 (trois fois l'écart de la v1) ne peut pas être atteint par un seul indicateur."""
    from bitumap.facteurs import chaleur

    v1 = _ecart_deciles([p.facteur("chaleur").effet for p in _calcul("1.2").points])
    mesures = {
        nom: _ecart_deciles(
            [p.facteur(nom).details.get("effet_si_retenu", 1.0) for p in _calcul("2.0").points]
        )
        for nom in chaleur.CANDIDATS
    }
    assert v1 == pytest.approx(0.1254, abs=1e-3)
    assert mesures[chaleur.ALEA] == pytest.approx(v1)
    assert mesures[chaleur.TEMPERATURE] == pytest.approx(0.1356, abs=1e-3)
    assert mesures[chaleur.MINERALISATION] == pytest.approx(0.0394, abs=1e-3)
    assert mesures[chaleur.CONTEXTE] == pytest.approx(0.1739, abs=1e-3)
    assert all(m <= chaleur.EFFET_MAX / chaleur.EFFET_MIN - 1 + 1e-9 for m in mesures.values())
