"""Altimétrie IGN (RGE ALTI, Licence Ouverte Etalab 2.0) : altitude de points (pentes)."""

from __future__ import annotations

from datetime import date

import httpx

from bitumap.sources.base import Provenance, client_http, obtenir

URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
LICENCE = "Licence Ouverte Etalab 2.0"
LOT = 150  # points par requête (URL de longueur raisonnable)
PROVENANCE_NOM = "IGN RGE ALTI (service d'altimétrie)"


def provenance() -> Provenance:
    return Provenance(
        PROVENANCE_NOM, LICENCE, "https://geoservices.ign.fr/rgealti", date.today(), "communale"
    )


def altitudes(
    points: list[tuple[float, float]], client: httpx.Client | None = None
) -> list[float | None]:
    """Altitudes (m) des points (lon, lat) ; ``None`` si inconnue (valeur -99999)."""
    fermer = client is None
    client = client or client_http(timeout=60)
    resultat: list[float | None] = []
    try:
        for i in range(0, len(points), LOT):
            morceau = points[i : i + LOT]
            reponse = obtenir(
                client,
                "Altimétrie IGN",
                URL,
                params={
                    "lon": "|".join(f"{x:.6f}" for x, _ in morceau),
                    "lat": "|".join(f"{y:.6f}" for _, y in morceau),
                    "resource": "ign_rge_alti_wld",
                    "zonly": "true",
                },
            )
            resultat += [None if z <= -9999 else float(z) for z in reponse.json()["elevations"]]
    finally:
        if fermer:
            client.close()
    return resultat
