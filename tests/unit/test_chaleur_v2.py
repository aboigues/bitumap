"""Indicateurs de chaleur de la 2.0 (004 T023, FR-005, FR-006) : candidats évalués un par
un, sans effet sur le score tant qu'ils ne sont pas retenus."""

from __future__ import annotations

import numpy as np
import pytest

from bitumap.facteurs import chaleur
from bitumap.score.methode import INDICATEURS_CHALEUR_RETENUS


def _par_nom(facteurs):
    return {f.nom: f for f in facteurs}


def test_aucun_indicateur_retenu_avant_validation():
    assert frozenset() == INDICATEURS_CHALEUR_RETENUS


def test_candidats_non_retenus_affiches_sans_effet():
    f = _par_nom(chaleur.candidats(12.0, "2.5", 36.4, 92.0, 2026, frozenset()))
    assert list(f) == list(chaleur.CANDIDATS)
    assert all(x.effet == 1.0 and x.statut == "evalue" for x in f.values())
    assert all(x.explication.endswith("non retenu (apport non démontré)") for x in f.values())
    assert all(x.details["retenu"] is False and not x.visible for x in f.values())
    assert f[chaleur.TEMPERATURE].valeur == 36.4 and f[chaleur.TEMPERATURE].details["ete"] == 2026
    assert f[chaleur.MINERALISATION].valeur == 92
    assert f[chaleur.CONTEXTE].valeur == "2"
    assert "bâti compact de hauteur moyenne" in f[chaleur.CONTEXTE].explication
    # L'effet qu'aurait l'indicateur, pour l'outil d'évaluation (R7).
    assert f[chaleur.TEMPERATURE].details["effet_si_retenu"] == pytest.approx(
        chaleur.effet_temperature(36.4), abs=1e-4
    )


def test_indicateur_retenu_effet_borne():
    retenus = frozenset({chaleur.TEMPERATURE, chaleur.MINERALISATION})
    f = _par_nom(chaleur.candidats(12.0, "A", 45.0, 100.0, 2026, retenus))
    assert f[chaleur.TEMPERATURE].effet == chaleur.EFFET_MAX  # borné au-delà de 38 °C
    assert f[chaleur.MINERALISATION].effet == chaleur.EFFET_MAX
    assert f[chaleur.ALEA].effet == 1.0 and f[chaleur.CONTEXTE].effet == 1.0  # non retenus
    assert not f[chaleur.TEMPERATURE].explication.endswith("(apport non démontré)")
    froid = _par_nom(chaleur.candidats(None, None, 10.0, 0.0, 2026, retenus))
    assert froid[chaleur.TEMPERATURE].effet == chaleur.EFFET_MIN
    assert froid[chaleur.MINERALISATION].effet == chaleur.EFFET_MIN


@pytest.mark.parametrize(
    ("celsius", "attendu"), [(28.0, 0.92), (33.0, 1.0), (38.0, 1.08), (20.0, 0.92)]
)
def test_effet_temperature(celsius, attendu):
    assert chaleur.effet_temperature(celsius) == pytest.approx(attendu)


def test_donnee_absente_non_evaluee():
    f = _par_nom(chaleur.candidats(-1.0, float("nan"), None, None, None, frozenset()))
    assert all(x.statut == "non_evalue" and x.effet == 1.0 for x in f.values())
    assert all("non évalué" in x.explication for x in f.values())


@pytest.mark.parametrize(
    ("lcz", "classe", "effet"),
    [
        ("2", "2", 1.08),
        ("5.2", "5", 1.0),
        ("B.5", "B", 0.92),
        ("10", "10", 1.08),
        ("e.b", "E", 1.08),
    ],
)
def test_contexte_urbain(lcz, classe, effet):
    assert chaleur.classe_lcz(lcz) == classe
    assert chaleur.effet_contexte(classe) == effet


def test_mineralisation_dans_50_m():
    vegetation = np.zeros((200, 200), dtype=bool)
    assert chaleur.mineralisation(vegetation) == 100.0
    vegetation[:, :100] = True  # moitié ouest arborée
    assert chaleur.mineralisation(vegetation) == pytest.approx(50.0, abs=1.5)
    loin = np.zeros((200, 200), dtype=bool)
    loin[:30, :] = True  # arbres à plus de 50 m du centre : sans effet
    assert chaleur.mineralisation(loin) == 100.0
    assert chaleur.mineralisation(None) is None


def test_canicules_jamais_facteur_de_classement():
    """L'été de référence (jours de forte chaleur) est identique pour tous les points d'une
    commune : il n'est pas un candidat (R4)."""
    noms = {f.nom for f in chaleur.candidats(10.0, "2", 30.0, 50.0, 2026, frozenset())}
    assert noms == set(chaleur.CANDIDATS)
    assert not any("canicule" in n or "forte_chaleur" in n for n in noms)


def test_chemin_1_2_inchange():
    f = chaleur.calculer(12.0, "2")
    assert (f.nom, f.valeur, f.effet) == ("chaleur", 12, chaleur.effet_alea(12.0))
    assert f.details == {}
