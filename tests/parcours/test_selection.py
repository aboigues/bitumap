"""Sélection des points dans la durée (006 T009, R3, FR-005, FR-006, SC-003) : fonctions
pures, durées simulées."""

from __future__ import annotations

import math

import pytest

from bitumap.parcours import selection
from bitumap.parcours.itineraire import Inaccessible

DEPART = (2.25, 48.89)


def _candidat(rang: int, lon: float, lat: float = 48.89, niveau: str = "P1a"):
    return selection.Candidat(f"A{rang}", rang, niveau, f"Point {rang}", lon, lat)


class _Durees:
    """Durée simulée : 1 s par mètre à vol d'oiseau (≈ 3,6 km/h) ; compte les appels."""

    def __init__(self, inaccessibles=()):
        self.appels = 0
        self.inaccessibles = set(inaccessibles)

    def __call__(self, a, b):
        self.appels += 1
        if a in self.inaccessibles or b in self.inaccessibles:
            raise Inaccessible
        metres = selection.vol_oiseau_m(a, b)
        return metres, metres  # (secondes, mètres)


def _choisir(candidats, duree_max_s, arret_s=300, durees=None, **kw):
    return selection.selectionner(
        DEPART, candidats, "pied", duree_max_s, arret_s, durees or _Durees(), **kw
    )


def test_ordre_du_rang_et_duree_tenue():
    # Le rang 2 est plus loin que le rang 3 : l'ordre du rang est gardé quand même (FR-005).
    candidats = [_candidat(1, 2.251), _candidat(2, 2.256), _candidat(3, 2.252)]
    s = _choisir(candidats, 3 * 3600)
    assert [v.rang for v in s.visites] == [1, 2, 3]
    assert [v.ordre for v in s.visites] == [1, 2, 3]
    assert s.duree_totale_s <= 3 * 3600  # trajets, arrêts et retour (SC-003)
    assert s.duree_restante_s == pytest.approx(3 * 3600 - s.duree_totale_s)
    assert s.non_visites == []


def test_point_trop_loin_saute_le_suivant_essaye():
    loin = _candidat(2, 2.40)  # environ 11 km à l'aller comme au retour
    candidats = [_candidat(1, 2.251), loin, _candidat(3, 2.252)]
    s = _choisir(candidats, 3600)
    assert [v.rang for v in s.visites] == [1, 3]
    assert [(n.rang, n.raison) for n in s.non_visites] == [(2, "duree")]
    assert s.duree_totale_s <= 3600


def test_prefiltre_a_vol_d_oiseau_sans_appel():
    durees = _Durees()
    candidats = [_candidat(1, 2.251), _candidat(2, 3.5)]  # 90 km : impossible à pied en 1 h
    s = _choisir(candidats, 3600, durees=durees)
    assert [(n.rang, n.raison) for n in s.non_visites] == [(2, "duree")]
    assert durees.appels == 2  # aller et retour du rang 1 seulement


def test_arret_quand_le_reste_est_inferieur_au_temps_d_arret():
    durees = _Durees()
    proche = [_candidat(r, 2.25 + r * 1e-5) for r in range(1, 30)]
    s = _choisir(proche, 31 * 60, arret_s=300, durees=durees)
    assert len(s.visites) == 6  # 6 arrêts de 5 min tiennent dans 31 min, pas 7
    assert all(n.raison == "duree" for n in s.non_visites)
    assert durees.appels <= 2 * 7


def test_au_plus_60_candidats_evalues():
    candidats = [_candidat(r, 2.25 + r * 1e-6) for r in range(1, 71)]
    s = _choisir(candidats, 8 * 3600, arret_s=60)
    assert len(s.visites) == 60
    assert [n.raison for n in s.non_visites] == ["limite_candidats"] * 10


def test_aucun_point():
    with pytest.raises(selection.AucunPoint):
        _choisir([], 3600)


def test_duree_insuffisante_avec_duree_minimale():
    candidats = [_candidat(1, 2.30), _candidat(2, 2.31)]  # 3,7 km : 1 h de marche à l'aller
    with pytest.raises(selection.DureeInsuffisante) as erreur:
        _choisir(candidats, 30 * 60)
    attendu = 2 * selection.vol_oiseau_m(DEPART, (2.30, 48.89)) + 300
    assert erreur.value.duree_min_s == pytest.approx(attendu)


def test_point_inaccessible():
    a2 = _candidat(2, 2.252)
    durees = _Durees(inaccessibles={(a2.lon, a2.lat)})
    s = _choisir([_candidat(1, 2.251), a2, _candidat(3, 2.253)], 3600, durees=durees)
    assert [v.rang for v in s.visites] == [1, 3]
    assert [(n.rang, n.raison) for n in s.non_visites] == [(2, "inaccessible")]


def test_cumuls_par_visite():
    candidats = [_candidat(1, 2.251), _candidat(2, 2.252)]
    s = _choisir(candidats, 3600, arret_s=120)
    d1 = selection.vol_oiseau_m(DEPART, (2.251, 48.89))
    d2 = selection.vol_oiseau_m((2.251, 48.89), (2.252, 48.89))
    assert s.visites[0].distance_cumulee_m == pytest.approx(d1)
    assert s.visites[1].duree_cumulee_s == pytest.approx(d1 + 120 + d2 + 120)
    retour = selection.vol_oiseau_m((2.252, 48.89), DEPART)
    assert s.duree_totale_s == pytest.approx(d1 + d2 + retour + 240)
    assert s.distance_totale_m == pytest.approx(d1 + d2 + retour)


def test_vol_oiseau():
    # 0,001° de longitude à 48,89° de latitude ≈ 73 m
    assert selection.vol_oiseau_m((2.25, 48.89), (2.251, 48.89)) == pytest.approx(
        111_195 * 0.001 * math.cos(math.radians(48.89)), rel=1e-3
    )
