"""Itinéraire de la Géoplateforme (006 T005, R2, R4) : réponses simulées, aucun réseau."""

from __future__ import annotations

import itertools

import httpx
import pytest
import respx

from bitumap.parcours import itineraire
from bitumap.sources.base import SourceIndisponible


def _point(texte: str) -> tuple[float, float]:
    lon, lat = texte.split(",")
    return float(lon), float(lat)


def _repondre(requete):
    """Simule le service : une portion par étape, 100 m et 60 s chacune ; refuse au-delà de
    15 intermédiaires comme le vrai service."""
    p = requete.url.params
    intermediaires = (
        [_point(x) for x in p["intermediates"].split("|")] if p.get("intermediates") else []
    )
    if len(intermediaires) > itineraire.MAX_INTERMEDIAIRES:
        return httpx.Response(400, json={"error": {"message": "max is 15"}})
    points = [_point(p["start"]), *intermediaires, _point(p["end"])]
    return httpx.Response(
        200,
        json={
            "profile": p["profile"],
            "distance": 100.0 * (len(points) - 1),
            "duration": 60.0 * (len(points) - 1),
            "geometry": {"type": "LineString", "coordinates": [list(x) for x in points]},
            "portions": [
                {
                    "start": f"{a[0]},{a[1]}",
                    "end": f"{b[0]},{b[1]}",
                    "distance": 100.0,
                    "duration": 60.0,
                }
                for a, b in itertools.pairwise(points)
            ],
        },
    )


class _Horloge:
    def __init__(self):
        self.t = 0.0
        self.attentes: list[float] = []

    def maintenant(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.attentes.append(s)
        self.t += s


def _limiteur() -> itineraire.Limiteur:
    h = _Horloge()
    return itineraire.Limiteur(horloge=h.maintenant, dormir=h.dormir)


@respx.mock
def test_un_trajet_profil_et_unites():
    route = respx.get(itineraire.URL).mock(side_effect=_repondre)
    with httpx.Client() as client:
        t = itineraire.trajet([(2.25, 48.89), (2.26, 48.90)], "pied", client, _limiteur())
    params = route.calls[0].request.url.params
    assert params["profile"] == "pedestrian" and params["resource"] == "bdtopo-osrm"
    assert params["distanceUnit"] == "meter" and params["timeUnit"] == "second"
    assert (t.distance_m, t.duree_s) == (100.0, 60.0)
    assert t.etapes == [(100.0, 60.0)]


@respx.mock
def test_plus_de_15_intermediaires_en_troncons_enchaines():
    route = respx.get(itineraire.URL).mock(side_effect=_repondre)
    depart = (2.25, 48.89)
    visites = [(2.25 + i * 0.001, 48.90) for i in range(30)]
    with httpx.Client() as client:
        t = itineraire.trajet([depart, *visites, depart], "voiture", client, _limiteur())
    assert route.call_count == 2  # 32 points : 17 + 16 (le point de jonction est partagé)
    assert len(t.etapes) == 31 and t.duree_s == 31 * 60.0
    # Aucun trou : la fin de chaque tronçon est le début du suivant.
    assert len(t.troncons) == 2 and t.troncons[0][-1] == t.troncons[1][0]
    assert t.geometrie[0] == list(depart) and t.geometrie[-1] == list(depart)
    for appel in route.calls:
        assert appel.request.url.params["profile"] == "car"


@respx.mock
def test_nouvelle_tentative_puis_indisponible(monkeypatch):
    monkeypatch.setattr("bitumap.sources.base.time.sleep", lambda s: None)
    route = respx.get(itineraire.URL).mock(
        side_effect=[httpx.Response(429), httpx.Response(503), _repondre]
    )
    with httpx.Client() as client:
        assert itineraire.trajet([(2.25, 48.89), (2.26, 48.9)], "voiture", client, _limiteur())
    assert route.call_count == 3
    respx.get(itineraire.URL).mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(SourceIndisponible):
        itineraire.trajet([(2.25, 48.89), (2.26, 48.9)], "voiture", client, _limiteur())


@respx.mock
def test_point_sans_itineraire_inaccessible():
    respx.get(itineraire.URL).mock(
        return_value=httpx.Response(400, json={"error": {"message": "no route found"}})
    )
    with httpx.Client() as client, pytest.raises(itineraire.Inaccessible):
        itineraire.trajet([(2.25, 48.89), (2.26, 48.9)], "pied", client, _limiteur())


def test_limiteur_quatre_requetes_par_seconde():
    h = _Horloge()
    limiteur = itineraire.Limiteur(horloge=h.maintenant, dormir=h.dormir)
    for _ in range(9):
        limiteur.attendre()
    assert h.t == pytest.approx(2.0)  # 9 requêtes à 0,25 s d'intervalle
    assert all(a == pytest.approx(0.25) for a in h.attentes)
