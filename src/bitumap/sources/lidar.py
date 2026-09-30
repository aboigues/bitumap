"""Modèles de hauteur LiDAR HD de l'IGN (Licence Ouverte Etalab 2.0), méthode 2.0 (004 R1).

Extraction **par point**, comme l'infrarouge de 1.x : carré de 200 m à 1 m autour du point,
MNS (altitude de tout ce qui dépasse du sol : bâti, arbres, ouvrages) et MNT (sol), en
Lambert 93, par ``GetMap`` GeoTIFF sur le WMS raster de la Géoplateforme (sans clé).
Le millésime (``code_mission`` et date de fin d'acquisition) est lu dans l'index des dalles
de 1 km, une fois par dalle ; il est affiché dans le rapport (R8) : un relevé d'hiver voit
les arbres sans feuilles.

Pas de cache : comme l'infrarouge, la requête est refaite à chaque rapport (≈ 0,8 s par
modèle et par point) ; la durée est suivie par SC-005.
"""

from __future__ import annotations

import math
from datetime import date

import httpx
import numpy as np
from rasterio.io import MemoryFile

from bitumap.sources.base import Hauteurs, Provenance, SourceIndisponible, obtenir

URL_WMS = "https://data.geopf.fr/wms-r/wms"
URL_WFS = "https://data.geopf.fr/wfs/ows"
LICENCE = "Licence Ouverte Etalab 2.0"
COUCHE = "IGNF_LIDAR-HD_{}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93"
INDEX = "IGNF_LIDAR-HD_METADONNEE:metadata"
DEMI_COTE_M = 100
RESOLUTION_M = 1.0
NODATA = -9999.0
PART_MIN_MESUREE = 0.5  # en dessous, zone considérée comme non couverte


def provenance() -> Provenance:
    return Provenance(
        "IGN LiDAR HD (modèles numériques de surface et de terrain)",
        LICENCE,
        "https://geoservices.ign.fr/lidarhd",
        date.today(),
        "communale",
    )


def dalle(x: float, y: float) -> str:
    """Identifiant de la dalle de 1 km contenant (x, y) : coin nord-ouest en km."""
    return f"{math.floor(x / 1000):04d}-{math.floor(y / 1000) + 1:04d}"


def _grille(client: httpx.Client, modele: str, x: float, y: float) -> np.ndarray | None:
    cote = int(2 * DEMI_COTE_M / RESOLUTION_M)
    reponse = obtenir(
        client,
        "IGN LiDAR HD",
        URL_WMS,
        params={
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": COUCHE.format(modele),
            "STYLES": "normal",
            "CRS": "EPSG:2154",
            "FORMAT": "image/geotiff",
            "BBOX": f"{x - DEMI_COTE_M},{y - DEMI_COTE_M},{x + DEMI_COTE_M},{y + DEMI_COTE_M}",
            "WIDTH": cote,
            "HEIGHT": cote,
        },
    )
    if not reponse.headers.get("content-type", "").startswith("image/"):
        return None  # exception du service (XML)
    with MemoryFile(reponse.content) as fichier, fichier.open() as ds:
        valeurs = ds.read(1).astype(np.float32)
    if valeurs.shape != (cote, cote):
        return None
    valeurs[valeurs <= NODATA + 1] = np.nan
    return valeurs


def _millesime(client: httpx.Client, x: float, y: float, memo: dict[str, str]) -> str | None:
    cle = dalle(x, y)
    if cle not in memo:
        reponse = obtenir(
            client,
            "IGN LiDAR HD (index des dalles)",
            URL_WFS,
            params={
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAMES": INDEX,
                "OUTPUTFORMAT": "application/json",
                "SRSNAME": "EPSG:2154",
                "BBOX": f"{x - 1},{y - 1},{x + 1},{y + 1},urn:ogc:def:crs:EPSG::2154",
                "COUNT": 5,
            },
        )
        entites = reponse.json().get("features", [])
        props = next(
            (f["properties"] for f in entites if f["properties"].get("coordonnees_nw") == cle),
            entites[0]["properties"] if entites else None,
        )
        if props is None:
            return None
        memo[cle] = f"{props['code_mission']} {str(props['date_fin_acquisition']).rstrip('Z')}"
    return memo[cle]


def hauteurs(x: float, y: float, client: httpx.Client, memo: dict[str, str]) -> Hauteurs | None:
    """MNS et MNT autour du point Lambert 93 (x, y) ; ``None`` si la zone n'est pas couverte
    ou si le service ne répond pas une image (repli sur la 1.2, spec « Edge Cases »)."""
    try:
        mns = _grille(client, "MNS", x, y)
        mnt = _grille(client, "MNT", x, y)
        if mns is None or mnt is None:
            return None
        if min(np.isfinite(mns).mean(), np.isfinite(mnt).mean()) < PART_MIN_MESUREE:
            return None
        millesime = _millesime(client, x, y, memo)
    except SourceIndisponible:
        return None
    if millesime is None:
        return None
    return Hauteurs(mns, mnt, (x - DEMI_COTE_M, y + DEMI_COTE_M), RESOLUTION_M, millesime)
