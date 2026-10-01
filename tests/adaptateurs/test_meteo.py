"""Données quotidiennes de Météo-France (004 T022, R4) : fichiers simulés, aucun réseau.

Seuils documentés (R4) : jour de forte chaleur = température maximale de 30 °C ou plus ;
35 °C ou plus compté à part. L'été de référence est affiché, jamais un facteur de classement.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import httpx
import pytest
import respx

from bitumap.sources import meteo
from bitumap.sources.base import SourceIndisponible
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"
ENTETE = "NUM_POSTE;NOM_USUEL;LAT;LON;ALTI;AAAAMMJJ;RR;QRR;TN;QTN;HTN;QHTN;TX;QTX"


def _fichier(lignes: list[tuple[str, str, str]]) -> bytes:
    corps = [ENTETE] + [
        f"{poste};{'MONTSOURIS' if poste == '75114001' else 'AUTRE'};48.8;2.3;75;"
        f"{jour};0;1;15;1;;;{tx};1"
        for poste, jour, tx in lignes
    ]
    return gzip.compress(("\n".join(corps) + "\n").encode())


CONTENU = _fichier(
    [
        ("75114001", "20260531", "36.0"),  # mai : hors été
        ("75114001", "20260601", "29.9"),
        ("75114001", "20260715", "30.0"),
        ("75114001", "20260716", "35.2"),
        ("75114001", "20260801", ""),  # manquant
        ("75114001", "20250801", "38.0"),  # autre été
        ("75106001", "20260715", "41.0"),  # autre station
    ]
)


def test_lecture_de_l_ete_a_la_station():
    nom, jours = meteo.lire_ete(CONTENU, "75114001", 2026)
    assert nom == "MONTSOURIS"
    assert [j["date"] for j in jours] == ["2026-06-01", "2026-07-15", "2026-07-16", "2026-08-01"]
    assert [j["tx"] for j in jours] == [29.9, 30.0, 35.2, None]


def test_bilan_jours_de_forte_chaleur():
    _, jours = meteo.lire_ete(CONTENU, "75114001", 2026)
    assert meteo.bilan(jours) == {
        "jours_mesures": 3,
        "jours_forte_chaleur": 2,
        "jours_tres_forte_chaleur": 1,
        "maximum_c": 35.2,
    }


def _jeu():
    base = "https://meteo.exemple.test/BASE/QUOT"
    return {
        "resources": [
            {"url": f"{base}/Q_75_previous-1950-2024_RR-T-Vent.csv.gz"},
            {"url": f"{base}/Q_75_latest-2025-2026_autres-parametres.csv.gz"},
            {"url": f"{base}/Q_75_latest-2025-2026_RR-T-Vent.csv.gz"},
            {"url": f"{base}/Q_92_latest-2025-2026_RR-T-Vent.csv.gz"},
        ]
    }


@respx.mock
def test_fichier_choisi_par_departement_et_periode():
    respx.get(meteo.URL_JEU).mock(return_value=httpx.Response(200, json=_jeu()))
    with httpx.Client() as client:
        assert meteo.fichier("75114001", 2026, client).endswith(
            "Q_75_latest-2025-2026_RR-T-Vent.csv.gz"
        )
        assert meteo.fichier("75114001", 2019, client).endswith(
            "Q_75_previous-1950-2024_RR-T-Vent.csv.gz"
        )
        with pytest.raises(SourceIndisponible):
            meteo.fichier("77001001", 2026, client)


@respx.mock
def test_station_sans_donnee_rend_none():
    respx.get(meteo.URL_JEU).mock(return_value=httpx.Response(200, json=_jeu()))
    respx.get(url__regex=r".*Q_75_latest-2025-2026_RR-T-Vent.*").mock(
        return_value=httpx.Response(200, content=CONTENU)
    )
    with httpx.Client() as client:
        assert meteo.meteo("75999999", 2026, client) is None
        provenance, jours = meteo.meteo("75114001", 2026, client)
    assert provenance.nom == (
        "Météo-France : données quotidiennes, station MONTSOURIS (75114001), été 2026"
    )
    assert meteo.nom_station(provenance) == "MONTSOURIS" and len(jours) == 4
    assert not provenance.hors_ue


def test_courbevoie_figee():
    provenance, jours = FournisseurFige(FIXTURES, "92026").meteo("75114001", 2026)
    assert meteo.nom_station(provenance) == "PARIS-MONTSOURIS"
    assert meteo.bilan(jours) == {
        "jours_mesures": 92,
        "jours_forte_chaleur": 39,
        "jours_tres_forte_chaleur": 20,
        "maximum_c": 40.6,
    }
