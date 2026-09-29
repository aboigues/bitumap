"""Fige les données d'une commune pour les tests (T022) : aucun accès réseau ensuite.

Usage : uv run python tools/figer_fixtures.py 92026 Courbevoie tests/fixtures/courbevoie
        uv run python tools/figer_fixtures.py --quais tests/fixtures/courbevoie
          (ajoute seulement la couche OSM « quais » à des fixtures existantes, T093)
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


def ajouter_quais(dossier: str) -> None:
    """Complète l'osm.gpkg figé avec la couche « quais » du même extrait régional, sans
    toucher aux autres couches (la non-régression reste comparable)."""
    import gzip
    import json

    import geopandas as gpd
    from shapely.geometry import shape

    from bitumap.calcul import _emprise

    with gzip.open(Path(dossier) / "contour.json.gz") as fichier:
        contour = json.loads(fichier.read())
    geom = contour["geometry"] if contour.get("type") == "Feature" else contour
    quais = gpd.read_file(_regional(), layer="quais", bbox=_emprise(shape(geom)))
    quais.to_file(Path(dossier) / "osm.gpkg", layer="quais", driver="GPKG")
    print(f"{len(quais)} quais -> {dossier}/osm.gpkg")


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
    if sys.argv[1] == "--quais":
        ajouter_quais(sys.argv[2])
    else:
        main(*sys.argv[1:4])
