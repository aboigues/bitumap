"""Ensoleillement de la chaussée à la mi-juillet (méthode 1.0, reprise du prototype).

Heures de soleil direct entre 8 h et 20 h (heure de Paris) le 15 juillet, par lancer de
rayons vers le soleil sur une grille de 1 m autour du point : hauteurs des bâtiments
(BD TOPO) et arbres (indice de végétation de l'infrarouge IGN, hauteur forfaitaire).
Effet : ×0,8 (jamais de soleil) à ×1,2 (12 h de soleil).

Le point est ramené sur la chaussée (voie bus la plus proche) : c'est l'enrobé qui chauffe,
pas le trottoir où se trouve le poteau d'arrêt (écart moyen au prototype : 1,15 h contre 2 h
mesuré au poteau, sur les 89 arrêts de Courbevoie).

Limites connues (traitées en 004) : échantillonnage en un point, hauteur forfaitaire des
arbres, pas de relief.
"""

from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import pvlib
from rasterio import features
from rasterio.transform import from_origin

from bitumap.modele import Facteur

DEMI_COTE_M = 100
HAUTEUR_ARBRE_M = 8.0
HAUTEUR_BATIMENT_DEFAUT_M = 10.0
ELEVATION_MIN_DEG = 2.0
HEURES_MAX = 12.0


@lru_cache(maxsize=4)
def positions_soleil(lat: float, lon: float) -> tuple[np.ndarray, np.ndarray]:
    """Azimut et élévation (degrés) aux 24 demi-heures centrées de 8 h à 20 h, 15 juillet."""
    instants = pd.date_range("2026-07-15 08:15", periods=24, freq="30min", tz="Europe/Paris")
    pos = pvlib.solarposition.get_solarposition(instants, round(lat, 2), round(lon, 2))
    return pos["azimuth"].to_numpy(), pos["apparent_elevation"].to_numpy()


def grille_hauteurs(
    x: float, y: float, batiments_l93: gpd.GeoDataFrame, vegetation: np.ndarray | None
) -> np.ndarray:
    """Grille (200 × 200, 1 m, nord en haut) des hauteurs d'obstacles autour de (x, y)."""
    cote = 2 * DEMI_COTE_M
    transform = from_origin(x - DEMI_COTE_M, y + DEMI_COTE_M, 1, 1)
    proches = batiments_l93.cx[x - DEMI_COTE_M : x + DEMI_COTE_M, y - DEMI_COTE_M : y + DEMI_COTE_M]
    grille = np.zeros((cote, cote), dtype=np.float32)
    if not proches.empty:
        hauteurs = proches["hauteur"].fillna(HAUTEUR_BATIMENT_DEFAUT_M).to_numpy()
        formes = [
            (g, float(h)) for g, h in zip(proches.geometry, hauteurs, strict=True) if g is not None
        ]
        if formes:
            grille = features.rasterize(
                formes, out_shape=(cote, cote), transform=transform, fill=0, dtype="float32"
            )
    if vegetation is not None and vegetation.shape == grille.shape:
        grille = np.where((grille == 0) & vegetation, HAUTEUR_ARBRE_M, grille)
    return grille


def decaler(masque: np.ndarray | None, dx_m: float, dy_m: float) -> np.ndarray | None:
    """Recentre un masque (1 m, nord en haut) sur un point décalé de (dx, dy) mètres ;
    les bords découverts sont considérés sans végétation."""
    if masque is None:
        return None
    dx, dy = round(dx_m), round(dy_m)
    resultat = np.zeros_like(masque)
    h, w = masque.shape
    lignes_src = slice(max(0, -dy), min(h, h - dy))
    lignes_dst = slice(max(0, dy), min(h, h + dy))
    cols_src = slice(max(0, dx), min(w, w + dx))
    cols_dst = slice(max(0, -dx), min(w, w - dx))
    resultat[lignes_dst, cols_dst] = masque[lignes_src, cols_src]
    return resultat


def heures_de_soleil(grille: np.ndarray, azimuts: np.ndarray, elevations: np.ndarray) -> float:
    centre = grille.shape[0] // 2
    distances = np.arange(2, DEMI_COTE_M, 1.0)
    ensoleillees = 0
    for az, el in zip(azimuts, elevations, strict=True):
        if el <= ELEVATION_MIN_DEG:
            continue
        a = np.radians(az)
        lignes = np.round(centre - distances * np.cos(a)).astype(int)
        colonnes = np.round(centre + distances * np.sin(a)).astype(int)
        dedans = (lignes >= 0) & (lignes < grille.shape[0]) & (colonnes >= 0)
        dedans &= colonnes < grille.shape[1]
        hauteur_rayon = distances * np.tan(np.radians(el))
        obstacle = grille[lignes[dedans], colonnes[dedans]] > hauteur_rayon[dedans]
        if not obstacle.any():
            ensoleillees += 1
    return ensoleillees * 0.5


def effet_heures(heures: float) -> float:
    return 0.8 + 0.4 * min(heures, HEURES_MAX) / HEURES_MAX


def calculer(
    lon: float,
    lat: float,
    x_l93: float,
    y_l93: float,
    batiments_l93: gpd.GeoDataFrame | None,
    vegetation: np.ndarray | None,
) -> Facteur:
    if batiments_l93 is None:
        return Facteur(
            "ensoleillement",
            None,
            1.0,
            statut="non_evalue",
            explication="Ensoleillement non évalué",
        )
    azimuts, elevations = positions_soleil(lat, lon)
    heures = heures_de_soleil(
        grille_hauteurs(x_l93, y_l93, batiments_l93, vegetation), azimuts, elevations
    )
    if heures >= 10:
        texte, visible = f"Plein soleil l'été : {heures:.1f} h/jour", True
    elif heures <= 3.5:
        texte, visible = f"Chaussée ombragée : {heures:.1f} h de soleil/jour", True
    else:
        texte, visible = f"Soleil l'été : {heures:.1f} h/jour", False
    return Facteur(
        "ensoleillement",
        heures,
        effet_heures(heures),
        provenance="estime",
        explication=texte + ("" if vegetation is not None else " (arbres non pris en compte)"),
        unite="h/jour",
        visible=visible,
    )
