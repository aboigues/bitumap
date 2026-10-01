"""Aides des tests du parcours : géocodage et itinéraire de l'IGN simulés (respx)."""

from __future__ import annotations

import itertools

import httpx
import respx

from bitumap.parcours import geocodage, itineraire, selection

HOTEL_DE_VILLE = ("2 Place De L'Hôtel De Ville 92400 Courbevoie", 2.256307, 48.895241, 0.96)
VITESSE_M_S = 8.0  # 29 km/h en ville, simulée à vol d'oiseau


def reponse_geocodage(*adresses) -> dict:
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


def _point(texte: str) -> tuple[float, float]:
    lon, lat = texte.split(",")
    return float(lon), float(lat)


def reponse_itineraire(requete: httpx.Request) -> httpx.Response:
    """Durée et distance à vol d'oiseau ; refuse au-delà de 15 intermédiaires, comme l'IGN."""
    p = requete.url.params
    milieu = [_point(x) for x in p["intermediates"].split("|")] if p.get("intermediates") else []
    if len(milieu) > itineraire.MAX_INTERMEDIAIRES:
        return httpx.Response(400, json={"error": {"message": "max is 15"}})
    points = [_point(p["start"]), *milieu, _point(p["end"])]
    portions = []
    for a, b in itertools.pairwise(points):
        m = selection.vol_oiseau_m(a, b)
        portions.append({"distance": m, "duration": m / VITESSE_M_S})
    return httpx.Response(
        200,
        json={
            "distance": sum(x["distance"] for x in portions),
            "duration": sum(x["duration"] for x in portions),
            "geometry": {"type": "LineString", "coordinates": [list(x) for x in points]},
            "portions": portions,
        },
    )


def simuler_ign(adresses=(HOTEL_DE_VILLE,)) -> None:
    """À appeler dans un contexte ``respx.mock`` actif."""
    respx.get(geocodage.URL).mock(
        return_value=httpx.Response(200, json=reponse_geocodage(*adresses))
    )
    respx.get(itineraire.URL).mock(side_effect=reponse_itineraire)
