"""Ensoleillement de la chaussée à la mi-juillet (méthode 1.2, reprise du prototype).

Heures de soleil direct entre 8 h et 20 h (heure de Paris) le 15 juillet, par lancer de
rayons vers le soleil sur une grille de 1 m autour du point : hauteurs des bâtiments
(BD TOPO), arbres (indice de végétation de l'infrarouge IGN, hauteur forfaitaire) et, depuis
la méthode 1.2, tabliers des ponts et passerelles (OpenStreetMap, issue #18) : une chaussée
sous un pont est à l'ombre.
Effet : ×0,8 (jamais de soleil) à ×1,2 (12 h de soleil).

Le point est ramené sur la chaussée (voie bus la plus proche) : c'est l'enrobé qui chauffe,
pas le trottoir où se trouve le poteau d'arrêt (écart moyen au prototype : 1,15 h contre 2 h
mesuré au poteau, sur les 89 arrêts de Courbevoie). Pour un arrêt, la mesure est la moyenne
de 5 points sur les 12 m où le bus s'arrête, en amont du poteau dans le sens de circulation
(6 m de part et d'autre sur une voie à double sens) : un poteau au bord d'un pont ne dit pas
l'ombre sous laquelle le bus s'arrête (méthode 1.2, issue #18).

Limites connues (traitées en 004) : hauteur forfaitaire des arbres, pas de relief ; zone
d'arrêt en ligne droite le long de la tangente de la voie.
"""

from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import pvlib
from rasterio import features
from rasterio.transform import from_origin
from shapely.geometry import Point as PointGeo

from bitumap.modele import Facteur

DEMI_COTE_M = 100
HAUTEUR_ARBRE_M = 8.0
HAUTEUR_BATIMENT_DEFAUT_M = 10.0
ELEVATION_MIN_DEG = 2.0
# Tabliers (méthode 1.2) : hauteur par niveau OSM (« layer ») et largeur faute de « width ».
HAUTEUR_TABLIER_M = 6.0
LARGEUR_TABLIER_M = {"rail": 5.0, "route": 8.0, "pieton": 3.0}
LIBELLES_OUVRAGE = {
    "rail": "un pont ferroviaire",
    "route": "un pont routier",
    "pieton": "une passerelle",
}
HEURES_MAX = 12.0


@lru_cache(maxsize=4)
def positions_soleil(lat: float, lon: float) -> tuple[np.ndarray, np.ndarray]:
    """Azimut et élévation (degrés) aux 24 demi-heures centrées de 8 h à 20 h, 15 juillet."""
    instants = pd.date_range("2026-07-15 08:15", periods=24, freq="30min", tz="Europe/Paris")
    pos = pvlib.solarposition.get_solarposition(instants, round(lat, 2), round(lon, 2))
    return pos["azimuth"].to_numpy(), pos["apparent_elevation"].to_numpy()


def tabliers(ouvrages_l93: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Emprise des tabliers (lignes OSM élargies) avec leur hauteur d'obstacle."""
    if ouvrages_l93 is None or ouvrages_l93.empty:
        return gpd.GeoDataFrame({"way_id": [], "genre": [], "hauteur": []}, geometry=[])
    largeurs = [
        float(w) if w == w and w else LARGEUR_TABLIER_M.get(g, 5.0)  # NaN ou vide ⇒ défaut
        for w, g in zip(ouvrages_l93.largeur_m, ouvrages_l93.genre, strict=True)
    ]
    return gpd.GeoDataFrame(
        {
            "way_id": ouvrages_l93.way_id.to_numpy(),
            "genre": ouvrages_l93.genre.to_numpy(),
            "hauteur": HAUTEUR_TABLIER_M * ouvrages_l93.niveau.clip(lower=1).to_numpy(),
        },
        geometry=ouvrages_l93.geometry.buffer([w / 2 for w in largeurs], cap_style="flat"),
        crs=ouvrages_l93.crs,
    )


def sous_ouvrage(x: float, y: float, tabliers_l93: gpd.GeoDataFrame | None) -> str | None:
    """Libellé de l'ouvrage au-dessus du point (x, y), s'il y en a un."""
    if tabliers_l93 is None or tabliers_l93.empty:
        return None
    dessus = tabliers_l93[tabliers_l93.contains(PointGeo(x, y))]
    return None if dessus.empty else LIBELLES_OUVRAGE.get(dessus.iloc[0].genre, "un ouvrage")


def _obstacles(
    x: float,
    y: float,
    demi: int,
    batiments_l93: gpd.GeoDataFrame,
    tabliers_l93: gpd.GeoDataFrame | None,
) -> np.ndarray:
    """Grille (2·demi mètres de côté, 1 m, nord en haut) des hauteurs des bâtiments et des
    tabliers autour de (x, y) ; une seule rasterisation, la plus haute forme l'emporte."""
    cote = 2 * demi
    fenetre = (slice(x - demi, x + demi), slice(y - demi, y + demi))
    formes = []
    proches = batiments_l93.cx[fenetre]
    if not proches.empty:
        hauteurs = proches["hauteur"].fillna(HAUTEUR_BATIMENT_DEFAUT_M).to_numpy()
        formes += [
            (g, float(h)) for g, h in zip(proches.geometry, hauteurs, strict=True) if g is not None
        ]
    if tabliers_l93 is not None and not tabliers_l93.empty:
        dessus = tabliers_l93.cx[fenetre]
        formes += [(g, float(h)) for g, h in zip(dessus.geometry, dessus.hauteur, strict=True)]
    if not formes:
        return np.zeros((cote, cote), dtype=np.float32)
    formes.sort(key=lambda forme: forme[1])  # dernière écrite = la plus haute
    return features.rasterize(
        formes,
        out_shape=(cote, cote),
        transform=from_origin(x - demi, y + demi, 1, 1),
        fill=0,
        dtype="float32",
    )


def _avec_arbres(grille: np.ndarray, vegetation: np.ndarray | None) -> np.ndarray:
    if vegetation is not None and vegetation.shape == grille.shape:
        return np.where((grille == 0) & vegetation, HAUTEUR_ARBRE_M, grille)
    return grille


def grille_hauteurs(
    x: float,
    y: float,
    batiments_l93: gpd.GeoDataFrame,
    vegetation: np.ndarray | None,
    tabliers_l93: gpd.GeoDataFrame | None = None,
) -> np.ndarray:
    """Grille (200 × 200, 1 m, nord en haut) des hauteurs d'obstacles autour de (x, y)."""
    return _avec_arbres(_obstacles(x, y, DEMI_COTE_M, batiments_l93, tabliers_l93), vegetation)


def grilles_zone(
    echantillons: list[tuple[float, float, np.ndarray | None]],
    batiments_l93: gpd.GeoDataFrame,
    tabliers_l93: gpd.GeoDataFrame | None,
) -> list[np.ndarray]:
    """Grilles de chaque point de mesure, découpées dans une seule grille élargie (une
    rasterisation par point du rapport au lieu d'une par point de mesure)."""
    x0, y0, _ = echantillons[0]
    decalages = [(round(x - x0), round(y - y0)) for x, y, _ in echantillons]
    marge = max(max(abs(dx), abs(dy)) for dx, dy in decalages)
    grande = _obstacles(x0, y0, DEMI_COTE_M + marge, batiments_l93, tabliers_l93)
    cote = 2 * DEMI_COTE_M
    grilles = []
    for (dx, dy), (_, _, vegetation) in zip(decalages, echantillons, strict=True):
        ligne, colonne = marge - dy, marge + dx  # nord en haut : y croissant = ligne décroissante
        grilles.append(
            _avec_arbres(grande[ligne : ligne + cote, colonne : colonne + cote], vegetation)
        )
    return grilles


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
    echantillons: list[tuple[float, float, np.ndarray | None]],
    batiments_l93: gpd.GeoDataFrame | None,
    tabliers_l93: gpd.GeoDataFrame | None = None,
) -> Facteur:
    """Heures de soleil moyennes sur les points de mesure (x, y, masque de végétation) :
    zone où le bus s'arrête pour un arrêt, point unique sinon (méthode 1.2)."""
    if batiments_l93 is None or not echantillons:
        return Facteur(
            "ensoleillement",
            None,
            1.0,
            statut="non_evalue",
            explication="Ensoleillement non évalué",
        )
    azimuts, elevations = positions_soleil(lat, lon)
    mesures = [
        heures_de_soleil(grille, azimuts, elevations)
        for grille in grilles_zone(echantillons, batiments_l93, tabliers_l93)
    ]
    heures = round(sum(mesures) / len(mesures), 1)
    ouvrages = [o for x, y, _ in echantillons if (o := sous_ouvrage(x, y, tabliers_l93))]
    zone = "Zone d'arrêt" if len(echantillons) > 1 else "Chaussée"
    if ouvrages:
        partiel = "en partie " if len(ouvrages) < len(echantillons) else ""
        texte = f"{zone} {partiel}sous {ouvrages[0]} : {heures:.1f} h de soleil/jour"
        visible = True
    elif heures >= 10:
        texte, visible = f"Plein soleil l'été : {heures:.1f} h/jour", True
    elif heures <= 3.5:
        texte, visible = f"Chaussée ombragée : {heures:.1f} h de soleil/jour", True
    else:
        texte, visible = f"Soleil l'été : {heures:.1f} h/jour", False
    sans_arbres = any(v is None for _, _, v in echantillons)
    return Facteur(
        "ensoleillement",
        heures,
        effet_heures(heures),
        provenance="estime",
        explication=texte + (" (arbres non pris en compte)" if sans_arbres else ""),
        unite="h/jour",
        visible=visible,
    )
