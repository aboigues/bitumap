"""Température de surface Landsat (004 T021, R3) : grilles synthétiques et réponses simulées,
aucun réseau ; Courbevoie figée pour la capture réelle."""

from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np
import pytest
import respx

from bitumap.sources import temperature
from bitumap.sources.base import Raster
from bitumap.sources.fournisseur import FournisseurFige

COURBEVOIE = (2.233, 48.886, 2.277, 48.914)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"


def _st(celsius: float) -> int:
    """Valeur brute de la bande ST_B10 pour une température en °C."""
    return round((celsius + 273.15 - temperature.DECALAGE) / temperature.ECHELLE)


DEGAGE = 1 << 6  # bit « clear »
NUAGE = (1 << 3) | (1 << 1)


def _scene(celsius: float, qa: int, forme=(4, 4)):
    return np.full(forme, _st(celsius), np.uint16), np.full(forme, qa, np.uint16)


def test_conversion_en_celsius():
    assert temperature.celsius(np.array([_st(35.0)], np.uint16))[0] == pytest.approx(35.0, abs=0.01)


def test_masque_des_nuages_ombres_eau():
    qa = np.array([DEGAGE, NUAGE, 1 << 4, 1 << 7, 1, 1 << 2], np.uint16)
    assert temperature.masque_degage(qa).tolist() == [True, False, False, False, False, False]


def test_mediane_des_scenes_degagees():
    chaude, _ = _scene(38.0, DEGAGE)
    nuageuse = _scene(20.0, NUAGE)  # entièrement couverte : écartée
    partielle_st, partielle_qa = _scene(30.0, DEGAGE)
    partielle_qa[0, :] = NUAGE  # 25 % masqués : retenue, ligne 0 ignorée
    v = temperature.mediane_ete(
        [(chaude, np.full((4, 4), DEGAGE, np.uint16)), nuageuse, (partielle_st, partielle_qa)]
    )
    assert v[0, 0] == pytest.approx(38.0, abs=0.01)  # seule la scène chaude est dégagée
    assert v[2, 2] == pytest.approx(34.0, abs=0.01)  # médiane de 38 et 30


def test_ete_sans_scene_exploitable():
    assert temperature.mediane_ete([_scene(20.0, NUAGE)]) is None
    assert temperature.mediane_ete([]) is None


def test_grille_lambert_93_alignee_sur_30_m():
    transform, largeur, hauteur = temperature.grille(COURBEVOIE)
    assert transform.a == 30.0 and transform.e == -30.0
    assert transform.c % 30 == 0 and transform.f % 30 == 0
    assert 90 < largeur < 130 and 90 < hauteur < 130


@respx.mock
def test_repli_sur_l_ete_precedent(monkeypatch):
    respx.get(temperature.URL_JETON).mock(return_value=httpx.Response(200, json={"token": "t"}))
    demandes = []

    def scenes(emprise, ete, client):
        demandes.append(ete)
        return [{"id": f"S{ete}", "assets": {"lwir11": {"href": "st"}, "qa_pixel": {"href": "qa"}}}]

    def lire(href, transform, largeur, hauteur):
        nuageux = "2026" in str(demandes[-1])
        if href.startswith("st"):
            return np.full((hauteur, largeur), _st(33.0), np.uint16)
        return np.full((hauteur, largeur), NUAGE if nuageux else DEGAGE, np.uint16)

    monkeypatch.setattr(temperature, "scenes", scenes)
    monkeypatch.setattr(temperature, "_lire", lire)
    with httpx.Client() as client:
        provenance, raster = temperature.temperature_surface(COURBEVOIE, 2026, client)
    assert demandes == [2026, 2025]
    assert raster.ete == 2025 and "été 2025" in provenance.nom
    assert np.nanmean(raster.valeurs) == pytest.approx(33.0, abs=0.01)


def test_provenance_hors_ue():
    p = temperature.provenance(2026)
    assert p.hors_ue and p.licence == "Domaine public (USGS)"
    assert "Planetary Computer" in p.nom and "été 2026" in p.nom


def test_valeur_au_point_fenetre_de_30_m():
    valeurs = np.full((5, 5), 30.0, np.float32)
    valeurs[2, 2] = 40.0
    valeurs[0, 0] = np.nan
    raster = Raster(valeurs, (0.0, 30.0, 0.0, 150.0, 0.0, -30.0), "EPSG:2154", 2026)
    # Centre du pixel (2, 2) : (75, 75) ; à 30 m : lui et ses 4 voisins directs.
    assert temperature.au_point(raster, 75.0, 75.0) == pytest.approx((40 + 4 * 30) / 5)
    assert temperature.au_point(raster, 15.0, 135.0, rayon_m=10) is None  # pixel sans mesure


def test_courbevoie_figee():
    provenance, raster = FournisseurFige(FIXTURES, "92026").temperature_surface(None, 2026)
    assert raster.ete == 2026 and provenance.hors_ue
    assert np.isfinite(raster.valeurs).mean() > 0.95
    assert 25 < np.nanmedian(raster.valeurs) < 40
    assert FournisseurFige(FIXTURES, "92026").temperature_surface(None, 2025) is None
