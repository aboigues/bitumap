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

**Méthode 2.0** (004, ``calculer_v2``, active si ``BITUMAP_METHODE=2.0``) : hauteurs
mesurées par le LiDAR HD (MNS : bâti, arbres, ouvrages ; MNT : sol, donc relief), soleil
heure par heure sur 6 jours de juin à août, et cause principale de l'ombre. Le LiDAR de
Courbevoie a été acquis en mars (arbres sans feuilles) : dans les cellules que l'infrarouge
classe en végétation, le houppier troué est comblé par la hauteur maximale voisine (R1).
Le MNS contient aussi des objets qui ne font pas d'ombre durable sur la chaussée (véhicules
présents lors du survol, mâts de feux, lampadaires) : objets de moins de 3 m de large effacés
et sursol de moins de 4 m ramené au sol (research R2, LL-016).
Sans hauteurs, repli sur la 1.2 pour le point, signalé.
"""

from __future__ import annotations

import warnings
from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import pvlib
from rasterio import features
from rasterio.transform import from_origin
from shapely.geometry import Point as PointGeo

from bitumap.modele import Facteur
from bitumap.sources.base import Hauteurs

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


# --- Méthode 2.0 (004) ------------------------------------------------------------------

# Période chaude (R2) : 1er et 15 de juin, juillet et août ; 12 instants horaires centrés de
# 8 h 30 à 19 h 30 (heure de Paris), soit 1 h de soleil par instant dégagé, 12 h au plus.
JOURS_ETE = ("2026-06-01", "2026-06-15", "2026-07-01", "2026-07-15", "2026-08-01", "2026-08-15")
HEURES_ETE = tuple(f"{h:02d}:30" for h in range(8, 20))
HAUTEUR_VEGETATION_MIN_M = 2.0
FENETRE_HOUPPIER = 5  # cellules : comblement du houppier troué d'un LiDAR d'hiver
# Sursol de moins de 4 m ramené au sol : véhicules présents lors du survol, abris ; au-delà
# de quelques mètres, un objet aussi bas ne cache que le soleil rasant (constaté à
# Courbevoie : véhicules de 2 à 3 m au bord des points de mesure).
SURSOL_MIN_M = 4.0
# Objets de moins de 3 m de large effacés (ouverture morphologique du sursol) : mâts de feux,
# lampadaires, potences captés par le LiDAR à 1 m, dont l'ombre fine ne couvre pas la chaussée
# (constaté aux feux de Courbevoie : « obstacles » de 8 à 16 m à 2 m du point).
FENETRE_OBJETS_FINS = 3
FENETRE_VEGETATION = 3  # tolérance de calage entre l'infrarouge et le LiDAR (cause « arbre »)
FENETRE_RUGOSITE = 5  # houppier : plus de 2 m d'écart entre cellules de sursol sur 5 × 5 m
CAUSES = ("batiment", "arbre", "ouvrage", "relief")
LIBELLES_CAUSE = {
    "batiment": "bâtiments",
    "arbre": "arbres",
    "ouvrage": "ouvrage d'art",
    "relief": "relief",
}
REPLI = "Ensoleillement estimé (données de hauteur incomplètes)"
MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def libelle_millesime(millesime: str) -> str:
    """« 22LHDKE 2023-03-03 » ⇒ « LiDAR HD de mars 2023 »."""
    try:
        annee, mois = millesime.split()[-1].split("-")[:2]
        return f"LiDAR HD de {MOIS[int(mois) - 1]} {annee}"
    except ValueError, IndexError:
        return "LiDAR HD"


@lru_cache(maxsize=4)
def positions_soleil_ete(lat: float, lon: float) -> tuple[np.ndarray, np.ndarray]:
    """Azimut et élévation (degrés) aux 72 instants de la période chaude."""
    instants = pd.DatetimeIndex([f"{j} {h}" for j in JOURS_ETE for h in HEURES_ETE]).tz_localize(
        "Europe/Paris"
    )
    pos = pvlib.solarposition.get_solarposition(instants, round(lat, 2), round(lon, 2))
    return pos["azimuth"].to_numpy(), pos["apparent_elevation"].to_numpy()


def _maximum_voisin(grille: np.ndarray, taille: int) -> np.ndarray:
    marge = taille // 2
    bord = np.pad(grille, marge, mode="edge")
    fenetres = np.lib.stride_tricks.sliding_window_view(bord, (taille, taille))
    return np.nanmax(fenetres, axis=(2, 3))


def _surface(h: Hauteurs, vegetation: np.ndarray | None) -> np.ndarray:
    """MNS où le houppier des arbres (végétation de l'infrarouge, plus de 2 m) est comblé,
    les objets fins effacés et le sursol bas (moins de ``SURSOL_MIN_M``) ramené au sol."""
    mns = np.where(np.isfinite(h.mns), h.mns, h.mnt)
    if vegetation is not None and vegetation.shape == mns.shape:
        voisin = _maximum_voisin(mns, FENETRE_HOUPPIER)
        # Une cellule trouée est au niveau du sol : c'est la hauteur voisine qui dit l'arbre.
        arbres = vegetation & (voisin - h.mnt > HAUTEUR_VEGETATION_MIN_M)
        mns = np.where(arbres, np.maximum(mns, voisin), mns)
    sursol = np.where(np.isfinite(h.mnt), mns - h.mnt, 0.0)
    sursol = _maximum_voisin(-_maximum_voisin(-sursol, FENETRE_OBJETS_FINS), FENETRE_OBJETS_FINS)
    sursol = np.where(sursol < SURSOL_MIN_M, 0.0, sursol)
    return np.where(np.isfinite(h.mnt), h.mnt + sursol, mns)


def _arbres_probables(
    vegetation: np.ndarray | None, surface: np.ndarray, mnt: np.ndarray
) -> np.ndarray:
    """Cellules dont l'obstacle est vraisemblablement un arbre (cause d'ombre) : végétation de
    l'infrarouge à 1 m près, ou sursol rugueux comme un houppier (plus de 2 m d'écart sur
    5 × 5 m) ; l'infrarouge manque les arbres à l'ombre des immeubles (constaté à
    Courbevoie, avenue Gambetta). Les emprises BD TOPO et les tabliers sont classés avant."""
    sursol = surface - mnt >= SURSOL_MIN_M
    # Rugosité mesurée entre cellules de sursol seulement : le bord d'un toit plat, où le toit
    # et la rue se côtoient, n'est pas rugueux.
    dessus = np.where(sursol, surface, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # fenêtres sans sursol
        haut = _maximum_voisin(dessus, FENETRE_RUGOSITE)
        bas = -_maximum_voisin(-dessus, FENETRE_RUGOSITE)
    arbres = sursol & (haut - bas >= HAUTEUR_VEGETATION_MIN_M)
    if vegetation is not None and vegetation.shape == surface.shape:
        arbres |= _maximum_voisin(vegetation.astype(np.uint8), FENETRE_VEGETATION).astype(bool)
    return arbres


def _classes(h: Hauteurs, batiments_l93, tabliers_l93) -> np.ndarray:
    """0 : autre, 1 : emprise de bâtiment (BD TOPO), 2 : tablier d'ouvrage (OSM)."""
    forme = h.mns.shape
    transform = from_origin(h.origine[0], h.origine[1], h.resolution, h.resolution)
    x0, y0 = h.origine
    fenetre = (slice(x0, x0 + forme[1] * h.resolution), slice(y0 - forme[0] * h.resolution, y0))
    formes = []
    if batiments_l93 is not None and not batiments_l93.empty:
        formes += [(g, 1) for g in batiments_l93.cx[fenetre].geometry if g is not None]
    if tabliers_l93 is not None and not tabliers_l93.empty:
        formes += [(g, 2) for g in tabliers_l93.cx[fenetre].geometry if g is not None]
    if not formes:
        return np.zeros(forme, dtype=np.uint8)
    classes = features.rasterize(
        formes, out_shape=forme, transform=transform, fill=0, dtype="uint8"
    )
    # Emprises élargies d'un mètre : le bord d'un toit capté par le LiDAR tombe souvent juste
    # hors de l'emprise BD TOPO (calage).
    bord = (classes == 0) & (_maximum_voisin((classes == 1).astype(np.uint8), 3) == 1)
    classes[bord] = 1
    return classes


def _cause(ligne, colonne, h: Hauteurs, sol_point, hauteur_rayon, classes, vegetation) -> str:
    if h.mnt[ligne, colonne] - sol_point > hauteur_rayon:
        return "relief"
    if classes[ligne, colonne] == 2:
        return "ouvrage"
    if classes[ligne, colonne] == 1:
        return "batiment"
    if vegetation is not None and vegetation.shape == classes.shape and vegetation[ligne, colonne]:
        return "arbre"
    return "batiment"  # construction non répertoriée (mur, abri…)


def _mesurer(x, y, h, surface, classes, vegetation, azimuts, elevations, sur_un_pont):
    """(heures de soleil par jour, causes des rayons bloqués) en (x, y) ; None si le sol y
    est inconnu."""
    ligne0 = int((h.origine[1] - y) / h.resolution)
    colonne0 = int((x - h.origine[0]) / h.resolution)
    forme = surface.shape
    if not (0 <= ligne0 < forme[0] and 0 <= colonne0 < forme[1]):
        return None
    sol_point = h.mns[ligne0, colonne0] if sur_un_pont else h.mnt[ligne0, colonne0]
    if not np.isfinite(sol_point):
        return None
    distances = np.arange(2, DEMI_COTE_M, 1.0)
    ensoleillees, causes = 0, []
    for az, el in zip(azimuts, elevations, strict=True):
        if el <= ELEVATION_MIN_DEG:
            continue
        a = np.radians(az)
        lignes = np.round(ligne0 - distances * np.cos(a) / h.resolution).astype(int)
        colonnes = np.round(colonne0 + distances * np.sin(a) / h.resolution).astype(int)
        dedans = (lignes >= 0) & (lignes < forme[0]) & (colonnes >= 0) & (colonnes < forme[1])
        lignes, colonnes = lignes[dedans], colonnes[dedans]
        rayon = distances[dedans] * np.tan(np.radians(el))
        bloque = surface[lignes, colonnes] - sol_point > rayon
        if not bloque.any():
            ensoleillees += 1
            continue
        i = int(np.argmax(bloque))  # premier obstacle rencontré
        causes.append(_cause(lignes[i], colonnes[i], h, sol_point, rayon[i], classes, vegetation))
    return ensoleillees / len(JOURS_ETE), causes


def calculer_v2(
    lon: float,
    lat: float,
    points_mesure: list[tuple[float, float]],
    hauteurs: Hauteurs | None,
    batiments_l93: gpd.GeoDataFrame | None,
    tabliers_l93: gpd.GeoDataFrame | None,
    vegetation: np.ndarray | None,
    sur_un_pont: bool = False,
    centre: tuple[float, float] | None = None,
) -> Facteur:
    """Heures de soleil moyennes de juin à août sur les points de mesure (Lambert 93), avec
    la cause principale de l'ombre (FR-001 à FR-004). ``vegetation`` : masque infrarouge
    centré, comme ``hauteurs``, sur ``centre`` (point du rapport ; défaut : premier point de
    mesure) ; ``sur_un_pont`` : le bus roule sur le tablier."""
    mesures = None
    if hauteurs is not None:
        azimuts, elevations = positions_soleil_ete(lat, lon)
        surface = _surface(hauteurs, vegetation)
        classes = _classes(hauteurs, batiments_l93, tabliers_l93)
        vegetation_large = _arbres_probables(vegetation, surface, hauteurs.mnt)
        mesures = [
            _mesurer(
                x, y, hauteurs, surface, classes, vegetation_large, azimuts, elevations, sur_un_pont
            )
            for x, y in points_mesure
        ]
        mesures = [m for m in mesures if m is not None] or None
    if mesures is None:
        return _repli(
            lon,
            lat,
            points_mesure,
            hauteurs,
            batiments_l93,
            tabliers_l93,
            vegetation,
            centre or points_mesure[0],
        )

    heures = round(sum(m[0] for m in mesures) / len(mesures), 1)
    toutes = [c for _, causes in mesures for c in causes]
    cause = max(CAUSES, key=toutes.count) if toutes else None
    ouvrages = [o for x, y in points_mesure if (o := sous_ouvrage(x, y, tabliers_l93))]
    zone = "Zone d'arrêt" if len(points_mesure) > 1 else "Chaussée"
    # FR-004 : la cause principale est dite dès qu'il y a de l'ombre (sous un ouvrage, le
    # libellé de l'ouvrage la dit déjà).
    ombre = f" ; ombre surtout due : {LIBELLES_CAUSE[cause]}" if cause else ""
    if ouvrages:
        partiel = "en partie " if len(ouvrages) < len(points_mesure) else ""
        texte = f"{zone} {partiel}sous {ouvrages[0]} : {heures:.1f} h de soleil/jour (juin–août)"
        visible = True
    elif heures >= 10:
        texte, visible = f"Plein soleil de juin à août : {heures:.1f} h/jour{ombre}", True
    elif heures <= 3.5:
        texte, visible = (
            f"Chaussée ombragée : {heures:.1f} h de soleil/jour (juin–août){ombre}",
            True,
        )
    else:
        texte, visible = f"Soleil de juin à août : {heures:.1f} h/jour{ombre}", False
    return Facteur(
        "ensoleillement",
        heures,
        effet_heures(heures),
        explication=f"{texte} ({libelle_millesime(hauteurs.millesime)})",
        unite="h/jour",
        visible=visible,
        details={"cause_ombre": cause, "source": "lidar_hd", "millesime_lidar": hauteurs.millesime},
    )


def _repli(
    lon, lat, points_mesure, hauteurs, batiments_l93, tabliers_l93, vegetation, centre
) -> Facteur:
    """Méthode 1.2 pour ce point, signalée (spec « Edge Cases »)."""
    f = calculer(
        lon,
        lat,
        [(x, y, decaler(vegetation, x - centre[0], y - centre[1])) for x, y in points_mesure],
        batiments_l93,
        tabliers_l93,
    )
    f.explication = f"{REPLI} : {f.explication}" if f.valeur is not None else REPLI
    f.details = {
        "cause_ombre": None,
        "source": "repli_1.2",
        "millesime_lidar": hauteurs.millesime if hauteurs is not None else None,
    }
    return f
