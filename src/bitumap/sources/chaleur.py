"""Îlots de chaleur urbains, Institut Paris Region 2022 (Licence Ouverte).

Champ ``aleaj_note`` : aléa de jour noté de 0 à 16 ; ``type_lcz`` : zone climatique locale.
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import httpx
import pandas as pd

from bitumap.sources.base import Extraction, Provenance, client_http, obtenir

URL = "https://geoweb.iau-idf.fr/agsmap1/rest/services/OPENDATA/OpendataIAU4/MapServer/13/query"
PAGE_ARCGIS = "https://data-iau-idf.opendata.arcgis.com/"
LICENCE = "Licence Ouverte (Institut Paris Region)"
PAGE = 1000


def acquerir(
    emprise: tuple[float, float, float, float], client: httpx.Client | None = None
) -> Extraction:
    fermer = client is None
    client = client or client_http(timeout=120)
    morceaux, decalage = [], 0
    try:
        while True:
            reponse = obtenir(
                client,
                "Îlots de chaleur",
                URL,
                params={
                    "geometry": ",".join(f"{v:.6f}" for v in emprise),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "outSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "aleaj_note,type_lcz",
                    "returnGeometry": "true",
                    "f": "geojson",
                    "resultOffset": decalage,
                    "resultRecordCount": PAGE,
                    "orderByFields": "objectid",
                },
            )
            entites = reponse.json().get("features", [])
            if entites:
                morceaux.append(gpd.GeoDataFrame.from_features(entites, crs="EPSG:4326"))
            if len(entites) < PAGE:
                break
            decalage += PAGE
    finally:
        if fermer:
            client.close()
    donnees = (
        gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs="EPSG:4326")
        if morceaux
        else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    )
    return Extraction(
        Provenance(
            "Institut Paris Region : îlots de chaleur urbains 2022",
            LICENCE,
            PAGE_ARCGIS,
            date(2022, 1, 1),
            "regionale",
        ),
        donnees,
    )
