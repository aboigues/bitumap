"""Construction des points à évaluer (FR-010, FR-016).

- arrêts de bus desservis dans la commune (offre IDFM) : ``A{id_arret}`` ;
- carrefours à feux traversés par au moins une ligne : feux OSM regroupés à 35 m,
  ``F{plus petit id de nœud}`` ;
- giratoires traversés par au moins une ligne : ``G{plus petit id de voie}``.

Charge d'une voie bus = Σ des passages quotidiens (par sens) des lignes qui l'empruntent,
multipliée par le nombre moyen de sens parcourus ; une ligne sans arrêt dans la commune
n'est pas comptée (limite du prototype).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from shapely.geometry import Point as PointGeo
from shapely.geometry import shape
from shapely.ops import unary_union

from bitumap.modele import Point
from bitumap.sources.idfm import ArretOffre

L93 = "EPSG:2154"
RAYON_FEU_VOIE_M = 12
RAYON_REGROUPEMENT_FEUX_M = 35
RAYON_VOIES_CARREFOUR_M = 20
RAYON_VOIE_ARRET_M = 30


@dataclass
class Reseau:
    """Voies bus de la commune, en Lambert 93, avec leur charge quotidienne."""

    voies: gpd.GeoDataFrame  # colonnes : way_id, nom, ref, lignes, charge, surface, pont, geometry


def polygone_commune(contour: dict):
    geom = contour["geometry"] if contour.get("type") == "Feature" else contour
    return shape(geom)


def feux_de_carrefour(feux: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Feux de carrefour seulement : les feux de traversée piétonne sont exclus."""
    if "pieton" not in feux.columns:
        return feux
    return feux[~feux.pieton.astype(bool)]


def charge_des_lignes(arrets: dict[str, ArretOffre]) -> dict[str, float]:
    """Passages quotidiens par sens de chaque ligne : médiane sur ses arrêts de la commune."""
    par_ligne: dict[str, list[float]] = {}
    for a in arrets.values():
        for ligne, jour in a.par_ligne_jour.items():
            par_ligne.setdefault(ligne, []).append(jour)
    return {ligne: statistics.median(v) for ligne, v in par_ligne.items()}


def reseau_bus(voies_bus: gpd.GeoDataFrame, commune, charges: dict[str, float]) -> Reseau:
    voies = voies_bus[voies_bus.intersects(commune)].copy()
    if voies.empty:
        voies = voies.assign(charge=[])
        return Reseau(voies.to_crs(L93))

    def charge(ligne):
        refs = [r for r in str(ligne.lignes).split(";") if r]
        if not refs:
            return 0.0
        sens = min(2.0, max(1.0, ligne.nb_itineraires / len(refs)))
        return sum(charges.get(r, 0.0) for r in refs) * sens

    voies["charge"] = voies.apply(charge, axis=1)
    return Reseau(voies.to_crs(L93))


def _nom_voie(reseau: Reseau, x: float, y: float, rayon: float) -> str:
    proches = reseau.voies[reseau.voies.distance(PointGeo(x, y)) <= rayon]
    proches = proches[proches.nom.astype(str) != ""]
    if proches.empty:
        return ""
    return str(proches.iloc[int(np.argmax(proches.charge.to_numpy()))].nom)


def _charge_carrefour(voies: gpd.GeoDataFrame) -> tuple[float, list[str]]:
    """Voie la plus chargée + moitié de la seconde (une valeur par rue)."""
    par_rue: dict[str, float] = {}
    for v in voies.itertuples():
        rue = str(v.nom or v.ref or v.way_id)
        par_rue[rue] = max(par_rue.get(rue, 0.0), float(v.charge))
    tri = sorted(par_rue.items(), key=lambda kv: -kv[1])
    if not tri:
        return 0.0, []
    charge = tri[0][1] + (0.5 * tri[1][1] if len(tri) > 1 else 0.0)
    return charge, [rue for rue, _ in tri]


def arrets(offre: dict[str, ArretOffre], reseau: Reseau, commune_l93) -> list[Point]:
    points = []
    geos = gpd.GeoSeries([PointGeo(a.lon, a.lat) for a in offre.values()], crs="EPSG:4326").to_crs(
        L93
    )
    for a, g in zip(offre.values(), geos, strict=True):
        if not commune_l93.contains(g):
            continue
        points.append(
            Point(
                id=f"A{a.id_arret}",
                type="arret",
                nom=a.nom,
                lon=a.lon,
                lat=a.lat,
                voie=_nom_voie(reseau, g.x, g.y, RAYON_VOIE_ARRET_M),
                bus_jour=round(a.bus_jour, 1),
                pointe_h=round(a.pointe_h, 1),
                lignes=a.lignes,
            )
        )
    return points


def _nom_carrefour(rues: list[str]) -> str:
    rues = [r for r in rues if r and not r.isdigit()]
    return " × ".join(rues[:2]) if len(rues) > 1 else (rues[0] if rues else "Carrefour")


def carrefours_a_feux(feux: gpd.GeoDataFrame, reseau: Reseau, commune_l93) -> list[Point]:
    if feux.empty or reseau.voies.empty:
        return []
    feux = feux.to_crs(L93)
    lignes_bus = unary_union(reseau.voies.geometry.to_list())
    feux = feux[feux.distance(lignes_bus) <= RAYON_FEU_VOIE_M]
    feux = feux[feux.within(commune_l93)]
    if feux.empty:
        return []
    # Regroupement des nœuds d'un même carrefour (union des disques de 35 m / 2).
    tampons = unary_union(feux.buffer(RAYON_REGROUPEMENT_FEUX_M / 2).to_list())
    groupes = list(getattr(tampons, "geoms", [tampons]))
    points = []
    for groupe in groupes:
        membres = feux[feux.within(groupe)]
        centre = membres.geometry.union_all().centroid
        voies = reseau.voies[reseau.voies.distance(centre) <= RAYON_VOIES_CARREFOUR_M]
        charge, rues = _charge_carrefour(voies)
        if charge <= 0:
            continue
        wgs = gpd.GeoSeries([centre], crs=L93).to_crs("EPSG:4326").iloc[0]
        lignes = sorted({r for v in voies.lignes for r in str(v).split(";") if r})
        points.append(
            Point(
                id=f"F{int(membres.node_id.min())}",
                type="feu",
                nom=_nom_carrefour(rues),
                lon=round(wgs.x, 6),
                lat=round(wgs.y, 6),
                voie=rues[0] if rues else "",
                bus_jour=round(charge, 1),
                lignes=lignes,
            )
        )
    return points


def giratoires(girs: gpd.GeoDataFrame, reseau: Reseau, commune_l93) -> list[Point]:
    if girs.empty or reseau.voies.empty:
        return []
    girs = girs.to_crs(L93)
    girs = girs[girs.intersects(commune_l93)]
    lignes_bus = unary_union(reseau.voies.geometry.to_list())
    girs = girs[girs.distance(lignes_bus) <= 5]
    if girs.empty:
        return []
    anneaux = unary_union(girs.buffer(10).to_list())
    points = []
    for anneau in getattr(anneaux, "geoms", [anneaux]):
        membres = girs[girs.intersects(anneau)]
        centre = anneau.centroid
        voies = reseau.voies[reseau.voies.intersects(anneau.buffer(15))]
        voies = voies[~voies.way_id.isin(membres.way_id)]  # voies d'accès, pas l'anneau
        charge, rues = _charge_carrefour(voies)
        if charge <= 0:
            continue
        wgs = gpd.GeoSeries([centre], crs=L93).to_crs("EPSG:4326").iloc[0]
        nom = next((str(n) for n in membres.nom if str(n)), "") or _nom_carrefour(rues)
        points.append(
            Point(
                id=f"G{int(membres.way_id.min())}",
                type="giratoire",
                nom=nom,
                lon=round(wgs.x, 6),
                lat=round(wgs.y, 6),
                voie=nom,
                bus_jour=round(charge, 1),
                lignes=sorted({r for v in voies.lignes for r in str(v).split(";") if r}),
            )
        )
    return points


def distance_carrefour_le_plus_proche(points: list[Point]) -> dict[str, float]:
    """Distance (m) de chaque arrêt au centre du carrefour à feux le plus proche.

    Règle du prototype (vérifiée : 26 arrêts sur 26 avec ses carrefours) : « arrêt à moins de
    40 m d'un feu » se mesure au centre des carrefours à feux, pas aux nœuds de feu OSM
    (qui incluent les feux de traversée piétonne)."""
    carrefours = [p for p in points if p.type == "feu"]
    arrets_ = [p for p in points if p.type == "arret"]
    if not carrefours or not arrets_:
        return {}
    c_l93 = gpd.GeoSeries([PointGeo(p.lon, p.lat) for p in carrefours], crs="EPSG:4326").to_crs(L93)
    centres = unary_union(c_l93.to_list())
    a_l93 = gpd.GeoSeries([PointGeo(p.lon, p.lat) for p in arrets_], crs="EPSG:4326").to_crs(L93)
    return {p.id: float(g.distance(centres)) for p, g in zip(arrets_, a_l93, strict=True)}
