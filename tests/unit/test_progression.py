"""Conversion de l'avancement du calcul en pourcentage et cadence d'écriture (009, contrat
§2) : logique pure, sans base."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from bitumap.lot.progression import BORNES, Progression, pourcentage


class Horloge:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _progression(horloge=None, maintenant=None):
    ecrits: list[tuple] = []
    p = Progression(
        lambda etape, avancement, fin: ecrits.append((etape, avancement, fin)),
        horloge=horloge or Horloge(),
        maintenant=maintenant or (lambda: datetime(2026, 10, 9, 12, tzinfo=UTC)),
    )
    return p, ecrits


def test_bornes_des_phases():
    assert BORNES == {"sources": (0, 5), "points": (5, 20), "ia": (20, 97), "rapport": (97, 99)}


@pytest.mark.parametrize(
    ("phase", "fait", "total", "attendu"),
    [
        ("sources", 0, 1, 0),
        ("sources", 1, 1, 5),
        ("points", 0, 270, 5),
        ("points", 135, 270, 12),
        ("points", 270, 270, 20),
        ("ia", 0, 54, 20),
        ("ia", 27, 54, 58),
        ("ia", 54, 54, 97),
        ("rapport", 0, 1, 97),
        ("rapport", 1, 1, 99),
    ],
)
def test_pourcentage(phase, fait, total, attendu):
    assert pourcentage(phase, fait, total) == attendu


def test_jamais_cent_ni_negatif():
    assert pourcentage("rapport", 5, 1) == 99
    assert pourcentage("sources", -3, 1) == 0


def test_total_nul_debut_de_phase():
    assert pourcentage("ia", 0, 0) == 20


def test_phase_inconnue_refusee():
    with pytest.raises(ValueError):
        pourcentage("calcul", 0, 1)


def test_ecriture_au_changement_de_phase_et_toutes_les_5_s():
    horloge = Horloge()
    p, ecrits = _progression(horloge)
    p("sources", 0, 1)
    p("sources", 1, 1)  # même phase, < 5 s : pas d'écriture
    p("points", 1, 10)  # changement de phase : la dernière valeur de « sources » d'abord
    assert [(e, a) for e, a, _ in ecrits] == [("sources", 0), ("sources", 5), ("points", 6)]
    horloge.t = 3
    p("points", 2, 10)
    assert len(ecrits) == 3
    horloge.t = 5.5
    p("points", 3, 10)
    assert ecrits[-1][:2] == ("points", 9)


def test_erreur_d_ecriture_ignoree(caplog):
    def ecrire(*_):
        raise RuntimeError("base indisponible")

    p = Progression(ecrire, horloge=Horloge())
    p("sources", 0, 1)  # ne lève pas
    assert "progression" in caplog.text


def test_pas_de_fin_estimee_hors_phase_ia():
    p, ecrits = _progression()
    p("sources", 0, 1)
    p("points", 1, 1)
    p("ia", 0, 4)
    assert all(fin is None for _, _, fin in ecrits)


def test_fin_estimee_pendant_les_analyses():
    horloge = Horloge()
    base = datetime(2026, 10, 9, 12, tzinfo=UTC)
    instant = {"t": base}
    p, ecrits = _progression(horloge, lambda: instant["t"])
    p("ia", 0, 4)
    horloge.t = 20.0  # 2 points en 20 s : 10 s par point
    instant["t"] = base + timedelta(seconds=20)
    p("ia", 2, 4)
    etape, avancement, fin = ecrits[-1]
    assert (etape, avancement) == ("ia", 58)
    assert fin == base + timedelta(seconds=20 + 2 * 10 + 15)
