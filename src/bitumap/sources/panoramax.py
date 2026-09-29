"""Panoramax : photos de rue (licence propre à chaque photo, relevée photo par photo)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import httpx

from bitumap.sources.base import Provenance, client_http, obtenir

URL = "https://api.panoramax.xyz/api/search"
# Visionneuse du méta-catalogue (panoramax.fr est le site du projet, pas une visionneuse).
URL_VISIONNEUSE = "https://api.panoramax.xyz/#focus=pic&pic={id}"


@dataclass(frozen=True)
class Photo:
    id: str
    date: str
    licence: str
    distance_m: float
    url: str


def provenance() -> Provenance:
    return Provenance(
        "Panoramax (photos de rue)",
        "licence propre à chaque photo",
        "https://panoramax.fr/",
        date.today(),
        "communale",
    )


def _distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    dx = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


def photo_la_plus_recente(
    lon: float, lat: float, rayon_m: float, client: httpx.Client | None = None
) -> Photo | None:
    """Photo la plus récente à moins de ``rayon_m`` mètres (FR-015)."""
    dlat = rayon_m / 110_540
    dlon = rayon_m / (111_320 * math.cos(math.radians(lat)))
    fermer = client is None
    client = client or client_http(timeout=30)
    try:
        reponse = obtenir(
            client,
            "Panoramax",
            URL,
            params={
                "bbox": f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}",
                "limit": 100,
            },
        )
    finally:
        if fermer:
            client.close()
    candidates = []
    for entite in reponse.json().get("features", []):
        x, y = entite["geometry"]["coordinates"][:2]
        distance = _distance_m(lon, lat, x, y)
        if distance <= rayon_m:
            p = entite["properties"]
            candidates.append(
                Photo(
                    entite["id"],
                    p.get("datetime", "")[:10],
                    p.get("license", "inconnue"),
                    round(distance, 1),
                    URL_VISIONNEUSE.format(id=entite["id"]),
                )
            )
    return max(candidates, key=lambda c: c.date, default=None)
