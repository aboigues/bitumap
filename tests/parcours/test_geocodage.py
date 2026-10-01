"""Adresse de départ (006 T004, R1, FR-003) : géocodage de la Géoplateforme simulé."""

from __future__ import annotations

import httpx
import pytest
import respx

from bitumap.parcours import geocodage
from bitumap.sources.base import SourceIndisponible


def _reponse(*adresses):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"label": libelle, "score": score},
            }
            for libelle, lon, lat, score in adresses
        ],
    }


HOTEL_DE_VILLE = ("2 Place De L'Hôtel De Ville 92400 Courbevoie", 2.256307, 48.895241, 0.96)
RUE = ("Rue De L'Hôtel De Ville 92400 Courbevoie", 2.256854, 48.89509, 0.71)


@respx.mock
def test_propositions_triees_par_score():
    route = respx.get(geocodage.URL).mock(
        return_value=httpx.Response(200, json=_reponse(RUE, HOTEL_DE_VILLE))
    )
    with httpx.Client() as client:
        adresses = geocodage.rechercher("2 place de l'hôtel de ville", client, autour=(2.25, 48.9))
    assert [a.libelle for a in adresses] == [HOTEL_DE_VILLE[0], RUE[0]]
    assert adresses[0] == geocodage.Adresse(*HOTEL_DE_VILLE)
    params = route.calls[0].request.url.params
    assert params["limit"] == "5" and params["index"] == "address"
    assert (params["lon"], params["lat"]) == ("2.250000", "48.900000")


@pytest.mark.parametrize("texte", ["", "  ", "ab"])
def test_texte_trop_court(texte):
    with httpx.Client() as client, pytest.raises(geocodage.TexteTropCourt):
        geocodage.rechercher(texte, client)


def test_choix_automatique_seulement_sans_ambiguite():
    sure = geocodage.Adresse(*HOTEL_DE_VILLE)
    proche = geocodage.Adresse("2 Place De L'Hôtel De Ville 92800 Puteaux", 2.24, 48.88, 0.93)
    assert geocodage.choix_automatique([sure]) == sure
    assert geocodage.choix_automatique([sure, geocodage.Adresse(*RUE)]) == sure
    assert geocodage.choix_automatique([sure, proche]) is None  # deux résultats proches
    assert geocodage.choix_automatique([geocodage.Adresse("x", 2.2, 48.8, 0.5)]) is None
    assert geocodage.choix_automatique([]) is None


@respx.mock
def test_service_en_erreur(monkeypatch):
    monkeypatch.setattr("bitumap.sources.base.time.sleep", lambda s: None)
    respx.get(geocodage.URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(SourceIndisponible):
        geocodage.rechercher("2 place de l'hôtel de ville", client)
