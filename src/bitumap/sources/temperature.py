"""Température de surface l'été, méthode 2.0 (004 R3, US2).

Produits Landsat 8-9 Collection 2 niveau 2 de l'USGS (« Surface Temperature », bande
thermique ré-échantillonnée à 30 m, domaine public), lus sur la **copie de Microsoft
Planetary Computer** : sans compte, jeton anonyme temporaire, fichiers stockés dans l'UE
(Azure West Europe) ; fournisseur américain : **service hors UE déclaré** (principe III ;
seule l'emprise de la commune est transmise). Choix du mainteneur du 2026-10-01 : l'accès
MACHINE de l'USGS n'a pas été accordé ; les valeurs sont les mêmes.

Méthode : scènes de juin à août de l'été de référence couvrant l'emprise, reprojetées sur une
grille Lambert 93 de 30 m ; pixels nuageux, ombre, eau ou neige masqués (``QA_PIXEL``) ;
scène retenue si au moins ``PART_DEGAGEE_MIN`` de l'emprise est dégagée ; médiane par pixel
en °C. Été sans scène retenue ⇒ été précédent, indiqué par ``Raster.ete``.

Pas de cache : une fenêtre par scène, lue à chaque rapport (0,4 à 1,3 s par scène, R3).
"""

from __future__ import annotations

import math
import warnings
from datetime import date

import httpx
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

from bitumap.sources.base import Provenance, Raster, SourceIndisponible, obtenir

URL_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
URL_JETON = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2"
COLLECTION = "landsat-c2-l2"
PLATEFORMES = ("landsat-8", "landsat-9")
PAGE_COLLECTION = "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"
LICENCE = "Domaine public (USGS)"
L93 = "EPSG:2154"
RESOLUTION_M = 30.0
# Bande ST_B10 : kelvins = valeur × échelle + décalage (métadonnées de la collection).
ECHELLE, DECALAGE = 0.00341802, 149.0
# Bits de QA_PIXEL : remplissage, nuage dilaté, cirrus, nuage, ombre, neige, eau.
BITS_MASQUES = (0, 1, 2, 3, 4, 5, 7)
PART_DEGAGEE_MIN = 0.5
MOIS_ETE = ("06-01", "08-31")

_VERS_L93 = Transformer.from_crs("EPSG:4326", L93, always_xy=True)


def provenance(ete: int | None = None) -> Provenance:
    suffixe = f", été {ete}" if ete else ""
    return Provenance(
        f"USGS Landsat Collection 2 niveau 2, température de surface (copie Microsoft "
        f"Planetary Computer){suffixe}",
        LICENCE,
        PAGE_COLLECTION,
        date.today(),
        "communale",
        hors_ue=True,
    )


def grille(emprise) -> tuple[tuple, int, int]:
    """Grille Lambert 93 de 30 m couvrant l'emprise (degrés), alignée sur 30 m."""
    xs, ys = _VERS_L93.transform([emprise[0], emprise[2]], [emprise[1], emprise[3]])
    x0 = math.floor(min(xs) / RESOLUTION_M) * RESOLUTION_M
    y1 = math.ceil(max(ys) / RESOLUTION_M) * RESOLUTION_M
    largeur = math.ceil((max(xs) - x0) / RESOLUTION_M)
    hauteur = math.ceil((y1 - min(ys)) / RESOLUTION_M)
    return from_origin(x0, y1, RESOLUTION_M, RESOLUTION_M), largeur, hauteur


def scenes(emprise, ete: int, client: httpx.Client) -> list[dict]:
    """Scènes Landsat 8-9 de l'été couvrant l'emprise, triées par identifiant."""
    reponse = obtenir(
        client,
        "Planetary Computer",
        URL_STAC,
        params={
            "collections": COLLECTION,
            "bbox": ",".join(f"{v:.6f}" for v in emprise),
            "datetime": f"{ete}-{MOIS_ETE[0]}T00:00:00Z/{ete}-{MOIS_ETE[1]}T23:59:59Z",
            "limit": 100,
        },
    )
    items = [
        i
        for i in reponse.json().get("features", [])
        if i.get("properties", {}).get("platform") in PLATEFORMES
        and {"lwir11", "qa_pixel"} <= set(i.get("assets", {}))
    ]
    return sorted(items, key=lambda i: i["id"])


def masque_degage(qa: np.ndarray) -> np.ndarray:
    """Pixels sans remplissage, nuage, ombre, neige ni eau."""
    masque = np.zeros(qa.shape, dtype=bool)
    for bit in BITS_MASQUES:
        masque |= (qa >> bit) & 1 == 1
    return ~masque


def celsius(st: np.ndarray) -> np.ndarray:
    return st.astype(np.float32) * np.float32(ECHELLE) + np.float32(DECALAGE - 273.15)


def _lire(href: str, transform, largeur: int, hauteur: int) -> np.ndarray:
    with (
        rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"),
        rasterio.open(href) as src,
        WarpedVRT(
            src,
            crs=L93,
            transform=transform,
            width=largeur,
            height=hauteur,
            resampling=Resampling.nearest,
            nodata=0,
        ) as vrt,
    ):
        return vrt.read(1)


def mediane_ete(couches: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray | None:
    """Médiane par pixel (°C) des scènes assez dégagées ; ``None`` si aucune ne l'est.

    ``couches`` : (valeurs ST brutes, QA_PIXEL) sur la même grille."""
    retenues = []
    for st, qa in couches:
        degage = masque_degage(qa) & (st > 0)
        if degage.mean() >= PART_DEGAGEE_MIN:
            retenues.append(np.where(degage, celsius(st), np.nan))
    if not retenues:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # pixel jamais dégagé : NaN
        return np.nanmedian(np.stack(retenues), axis=0).astype(np.float32)


def _ete(emprise, ete: int, client: httpx.Client, jeton: str) -> Raster | None:
    transform, largeur, hauteur = grille(emprise)
    couches = []
    for item in scenes(emprise, ete, client):
        try:
            st = _lire(f"{item['assets']['lwir11']['href']}?{jeton}", transform, largeur, hauteur)
            qa = _lire(f"{item['assets']['qa_pixel']['href']}?{jeton}", transform, largeur, hauteur)
        except rasterio.errors.RasterioIOError as erreur:
            raise SourceIndisponible("Planetary Computer", type(erreur).__name__) from erreur
        couches.append((st, qa))
    valeurs = mediane_ete(couches)
    if valeurs is None:
        return None
    return Raster(valeurs, tuple(transform.to_gdal()), L93, ete)


def temperature_surface(
    emprise, ete: int, client: httpx.Client
) -> tuple[Provenance, Raster] | None:
    """Médiane de l'été de référence, sinon de l'été précédent ; ``None`` si aucun des deux
    n'a de scène exploitable."""
    jeton = obtenir(client, "Planetary Computer", URL_JETON).json()["token"]
    for annee in (ete, ete - 1):
        raster = _ete(emprise, annee, client, jeton)
        if raster is not None:
            return provenance(annee), raster
    return None


def au_point(raster: Raster, x: float, y: float, rayon_m: float = 30.0) -> float | None:
    """Moyenne des pixels dont le centre est à moins de ``rayon_m`` du point (Lambert 93)."""
    x0, dx, _, y0, _, dy = raster.transform
    lignes, colonnes = np.indices(raster.valeurs.shape)
    cx = x0 + (colonnes + 0.5) * dx
    cy = y0 + (lignes + 0.5) * dy
    proches = (cx - x) ** 2 + (cy - y) ** 2 <= rayon_m**2
    valeurs = raster.valeurs[proches]
    valeurs = valeurs[np.isfinite(valeurs)]
    return float(valeurs.mean()) if valeurs.size else None
