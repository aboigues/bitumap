"""IGN BD TOPO (Licence Ouverte Etalab 2.0) via le WFS de la Géoplateforme.

- ``troncon_de_route`` : classement administratif, gestionnaire, numéro (type de route, FR-013) ;
- ``batiment`` : hauteurs (ombres, facteur d'ensoleillement).
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import httpx

from bitumap.sources.base import Extraction, Provenance, client_http, obtenir

URL_WFS = "https://data.geopf.fr/wfs/ows"
LICENCE = "Licence Ouverte Etalab 2.0"
PAGE = 5000
CHAMPS_TRONCON = (
    "cpx_classement_administratif",
    "cpx_gestionnaire",
    "cpx_numero",
    "importance",
    "urbain",
    "nom_voie_ban_gauche",
    "nom_voie_ban_droite",
    "nature",
)


def _obtenir_couche(
    client: httpx.Client, couche: str, emprise: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = emprise
    morceaux, debut = [], 0
    while True:
        reponse = obtenir(
            client,
            "BD TOPO",
            URL_WFS,
            params={
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAMES": couche,
                "OUTPUTFORMAT": "application/json",
                "SRSNAME": "EPSG:4326",
                "BBOX": f"{miny},{minx},{maxy},{maxx},urn:ogc:def:crs:EPSG::4326",
                "COUNT": PAGE,
                "STARTINDEX": debut,
                "SORTBY": "cleabs",
            },
        )
        entites = reponse.json().get("features", [])
        if entites:
            morceaux.append(gpd.GeoDataFrame.from_features(entites, crs="EPSG:4326"))
        if len(entites) < PAGE:
            break
        debut += PAGE
    if not morceaux:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    import pandas as pd

    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs="EPSG:4326")


def acquerir(
    emprise: tuple[float, float, float, float], client: httpx.Client | None = None
) -> Extraction:
    fermer = client is None
    client = client or client_http(timeout=120)
    try:
        troncons = _obtenir_couche(client, "BDTOPO_V3:troncon_de_route", emprise)
        batiments = _obtenir_couche(client, "BDTOPO_V3:batiment", emprise)
    finally:
        if fermer:
            client.close()
    garder = [c for c in (*CHAMPS_TRONCON, "geometry") if c in troncons.columns]
    batiments = batiments[[c for c in ("hauteur", "geometry") if c in batiments.columns]]
    return Extraction(
        Provenance(
            "IGN BD TOPO (tronçons de route, bâtiments)",
            LICENCE,
            "https://geoservices.ign.fr/bdtopo",
            date.today(),
            "communale",
        ),
        {"troncons": troncons[garder], "batiments": batiments},
    )
