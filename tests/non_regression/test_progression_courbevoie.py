"""Avancement signalé par le calcul de Courbevoie, sur les données figées (009, contrat §1) :
ordre des phases, un appel par point, et aucun effet sur le résultat (principe IV)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from bitumap.calcul import calculer_commune
from bitumap.lot.progression import pourcentage
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"


def _calculer(avancement=None):
    p1: list[int] = []
    resultat = calculer_commune(
        FournisseurFige(FIXTURES, "92026"),
        "Courbevoie",
        analyse_ia=lambda points: p1.append(len(points)),
        methode="1.2",
        avancement=avancement,
    )
    return resultat, p1


@cache
def _avec_avancement():
    appels: list[tuple[str, int, int]] = []
    resultat, p1 = _calculer(lambda *args: appels.append(args))
    return resultat, appels, p1


def test_phases_dans_l_ordre_un_appel_par_point():
    resultat, appels, _ = _avec_avancement()
    n = len(resultat.points)
    assert appels[:2] == [("sources", 0, 1), ("sources", 1, 1)]
    assert appels[2:] == [("points", i, n) for i in range(1, n + 1)]


def test_pourcentages_croissants():
    _, appels, _ = _avec_avancement()
    valeurs = [pourcentage(*a) for a in appels]
    assert valeurs == sorted(valeurs)
    assert valeurs[-1] == 20  # fin de la phase « points », début des analyses par l'IA


def test_resultat_identique_avec_et_sans_avancement():
    avec, _, p1_avec = _avec_avancement()
    sans, p1_sans = _calculer()
    assert p1_avec == p1_sans
    assert [(p.id, p.priorite, p.score) for p in avec.points] == [
        (p.id, p.priorite, p.score) for p in sans.points
    ]
