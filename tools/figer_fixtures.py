"""Fige les données d'une commune pour les tests (T022) : aucun accès réseau ensuite.

Usage : uv run python tools/figer_fixtures.py 92026 Courbevoie tests/fixtures/courbevoie
        uv run python tools/figer_fixtures.py --couches tests/fixtures/courbevoie quais ouvrages
          (ajoute seulement ces couches OSM à des fixtures existantes : quais T093,
          ouvrages issue #18)
        uv run python tools/figer_fixtures.py --hauteurs tests/fixtures/courbevoie 92026 Courbevoie
          (ajoute seulement les hauteurs LiDAR HD des points, méthode 2.0 : 004 T016)
Prérequis : extrait OSM régional (var/cache/osm-idf-AAMMJJ-vN.gpkg).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from bitumap.calcul import calculer_commune
from bitumap.sources import osm
from bitumap.sources.fournisseur import Enregistreur, FournisseurEnLigne


def reduire(dossier: Path, resultat) -> None:
    """Ne garde que les objets BD TOPO utiles au calcul (dépôt léger) : bâtiments à moins de
    180 m d'un point (grille d'ombre de ±100 m, coins à 141 m, point recentré sur la
    chaussée jusqu'à 30 m) et tronçons à moins de 60 m (type de route)."""
    import geopandas as gpd
    from shapely.geometry import Point

    pts = gpd.GeoSeries([Point(p.lon, p.lat) for p in resultat.points], crs="EPSG:4326").to_crs(
        "EPSG:2154"
    )
    fichier = dossier / "bdtopo.gpkg"
    couches = {c: gpd.read_file(fichier, layer=c) for c in ("troncons", "batiments")}
    fichier.unlink()
    for couche, rayon in (("troncons", 60), ("batiments", 180)):
        zone = pts.buffer(rayon).union_all()
        gdf = couches[couche]
        garde = gdf[gdf.to_crs("EPSG:2154").intersects(zone)]
        garde.to_file(fichier, layer=couche, driver="GPKG")


def _regional() -> Path:
    return sorted(Path("var/cache").glob(f"osm-idf-*-v{osm.VERSION_CACHE}.gpkg"))[-1]


def ajouter_couches(dossier: str, couches: list[str]) -> None:
    """Complète l'osm.gpkg figé avec des couches du même extrait régional, sans toucher aux
    autres (la non-régression reste comparable)."""
    import gzip
    import json

    import geopandas as gpd
    from shapely.geometry import shape

    from bitumap.calcul import _emprise

    with gzip.open(Path(dossier) / "contour.json.gz") as fichier:
        contour = json.loads(fichier.read())
    geom = contour["geometry"] if contour.get("type") == "Feature" else contour
    for couche in couches:
        gdf = gpd.read_file(_regional(), layer=couche, bbox=_emprise(shape(geom)))
        gdf.to_file(Path(dossier) / "osm.gpkg", layer=couche, driver="GPKG")
        print(f"{len(gdf)} {couche} -> {dossier}/osm.gpkg")


def ajouter_hauteurs(dossier: str, insee: str, nom: str) -> None:
    """Fige les hauteurs LiDAR HD (004 T016) des points d'une commune déjà figée, sans
    toucher aux autres sources : la non-régression 1.2 reste comparable."""
    from bitumap.sources import lidar
    from bitumap.sources.base import client_http
    from bitumap.sources.fournisseur import _VERS_L93, FournisseurFige, _cle, ecrire_hauteurs

    t0 = time.perf_counter()
    points = calculer_commune(FournisseurFige(Path(dossier), insee), nom).points
    memo: dict[str, str] = {}
    hauteurs = {}
    with client_http(timeout=120) as client:
        for p in points:
            lon, lat = round(p.lon, 6), round(p.lat, 6)
            h = lidar.hauteurs(*_VERS_L93.transform(lon, lat), client, memo)
            if h is not None:
                hauteurs[_cle(lon, lat)] = h
    ecrire_hauteurs(Path(dossier) / "hauteurs.npz", hauteurs)
    taille = (Path(dossier) / "hauteurs.npz").stat().st_size / 1e6
    print(
        f"{len(hauteurs)}/{len(points)} points, {len(memo)} dalles, {taille:.1f} Mo, "
        f"{time.perf_counter() - t0:.0f} s -> {dossier}/hauteurs.npz"
    )


def main(insee: str, nom: str, dossier: str) -> None:
    regional = _regional()
    date_osm = datetime.strptime(regional.stem.split("-")[2], "%y%m%d").date()
    en_ligne = FournisseurEnLigne(insee, regional, date_osm)
    enregistreur = Enregistreur(en_ligne, Path(dossier))
    t0 = time.perf_counter()
    resultat = calculer_commune(enregistreur, nom)
    enregistreur.terminer()
    en_ligne.fermer()
    reduire(Path(dossier), resultat)
    print(f"{len(resultat.points)} points en {time.perf_counter() - t0:.0f} s -> {dossier}")
    for avertissement in resultat.avertissements:
        print("avertissement :", avertissement)


if __name__ == "__main__":
    if sys.argv[1] == "--couches":
        ajouter_couches(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "--hauteurs":
        ajouter_hauteurs(*sys.argv[2:5])
    else:
        main(*sys.argv[1:4])
