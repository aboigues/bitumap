"""Orthophotos IGN (Licence Ouverte Etalab 2.0) via le WMS raster de la Géoplateforme.

- infrarouge couleur : indice de végétation (arbres) pour l'ensoleillement ;
- millésimes annuels : vignettes pour l'estimation de l'âge de l'enrobé (points P1).
"""

from __future__ import annotations

import io
import math
from datetime import date

import httpx
import numpy as np
from PIL import Image

from bitumap.sources.base import Provenance, client_http, obtenir

URL_WMS = "https://data.geopf.fr/wms-r/wms"
LICENCE = "Licence Ouverte Etalab 2.0"
COUCHE_IRC = "ORTHOIMAGERY.ORTHOPHOTOS.IRC"
MILLESIMES = (2003, 2006, 2008, 2011, 2014, 2017, 2018, 2020, 2021, 2023, 2024)


def provenance() -> Provenance:
    return Provenance(
        "IGN orthophotos (infrarouge couleur, millésimes historiques)",
        LICENCE,
        "https://geoservices.ign.fr/bdortho",
        date.today(),
        "communale",
    )


def _emprise_metrique(lon: float, lat: float, demi_cote_m: float) -> tuple[float, ...]:
    dlat = demi_cote_m / 110_540
    dlon = demi_cote_m / (111_320 * math.cos(math.radians(lat)))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)  # ordre WMS 1.3.0 EPSG:4326


def image(
    couche: str, lon: float, lat: float, demi_cote_m: float, pixels: int, client: httpx.Client
) -> Image.Image | None:
    reponse = obtenir(
        client,
        "Orthophotos IGN",
        URL_WMS,
        params={
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": couche,
            "STYLES": "",
            "CRS": "EPSG:4326",
            "FORMAT": "image/jpeg",
            "BBOX": ",".join(f"{v:.7f}" for v in _emprise_metrique(lon, lat, demi_cote_m)),
            "WIDTH": pixels,
            "HEIGHT": pixels,
        },
    )
    if not reponse.headers.get("content-type", "").startswith("image/"):
        return None
    img = Image.open(io.BytesIO(reponse.content)).convert("RGB")
    tableau = np.asarray(img)
    if tableau.std() < 2:  # image uniforme : millésime non couvert à cet endroit
        return None
    return img


def masque_vegetation(
    lon: float, lat: float, demi_cote_m: float, resolution_m: float, client: httpx.Client
) -> np.ndarray | None:
    """Masque booléen des arbres (NDVI > 0,2) autour d'un point, nord en haut."""
    pixels = int(2 * demi_cote_m / resolution_m)
    img = image(COUCHE_IRC, lon, lat, demi_cote_m, pixels, client)
    if img is None:
        return None
    irc = np.asarray(img, dtype=np.float32)
    proche_ir, rouge = irc[..., 0], irc[..., 1]  # IRC : canal 1 = proche infrarouge, 2 = rouge
    ndvi = (proche_ir - rouge) / np.maximum(proche_ir + rouge, 1)
    return ndvi > 0.2


def vignettes_historiques(
    lon: float,
    lat: float,
    client: httpx.Client | None = None,
    demi_cote_m: float = 40,
    pixels: int = 512,
) -> list[tuple[int, Image.Image]]:
    """Vignettes 512×512 px des millésimes disponibles à cet endroit (âge de l'enrobé)."""
    fermer = client is None
    client = client or client_http(timeout=60)
    resultat = []
    try:
        for annee in MILLESIMES:
            img = image(f"ORTHOIMAGERY.ORTHOPHOTOS{annee}", lon, lat, demi_cote_m, pixels, client)
            if img is not None:
                resultat.append((annee, img))
    finally:
        if fermer:
            client.close()
    return resultat
