"""Fige les données d'une commune pour les tests (T022) : aucun accès réseau ensuite.

Usage : uv run python tools/figer_fixtures.py 92026 Courbevoie tests/fixtures/courbevoie
Prérequis : extrait OSM régional (var/cache/osm-idf-AAMMJJ.gpkg).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from bitumap.calcul import calculer_commune
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


def main(insee: str, nom: str, dossier: str) -> None:
    regional = sorted(Path("var/cache").glob("osm-idf-*.gpkg"))[-1]
    date_osm = datetime.strptime(regional.stem.rsplit("-", 1)[1], "%y%m%d").date()
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
    main(*sys.argv[1:4])
