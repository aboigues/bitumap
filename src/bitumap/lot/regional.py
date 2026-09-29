"""Données régionales, acquises une fois par lot et au plus une fois par jour (FR-007b).

L'extrait OSM compact (≈ 36 Mo) est mis en cache dans le stockage objet : sa reconstruction
(≈ 3 min) n'a lieu qu'à la parution d'un nouvel extrait Geofabrik.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bitumap import stockage
from bitumap.config import reglages
from bitumap.lot import versions
from bitumap.sources import idfm, osm
from bitumap.sources.base import client_http


@dataclass
class DonneesRegionales:
    osm_gpkg: Path
    osm_date: date
    duree_s: float


def _osm(dossier: Path) -> tuple[Path, date]:
    pbf, date_osm = osm.telecharger(dossier)
    gpkg = dossier / f"osm-idf-{date_osm:%y%m%d}-v{osm.VERSION_CACHE}.gpkg"
    cle = f"regional/osm/{gpkg.name}"
    bucket = reglages().bucket_cache
    if not gpkg.exists():
        contenu = stockage.lire(bucket, cle)
        if contenu is not None:
            gpkg.write_bytes(contenu)
        else:
            osm.enregistrer(osm.extraire_region(pbf), gpkg)
            stockage.ecrire(bucket, cle, gpkg.read_bytes(), "application/geopackage+sqlite3")
    return gpkg, date_osm


def preparer(dossier: Path) -> DonneesRegionales:
    t0 = time.perf_counter()
    dossier.mkdir(parents=True, exist_ok=True)
    gpkg, date_osm = _osm(dossier)
    versions.enregistrer("osm", date_osm)
    with client_http() as client:
        versions.enregistrer("idfm", idfm.date_mise_a_jour(client))
    versions.enregistrer("chaleur", versions.VERSION_CHALEUR)
    return DonneesRegionales(gpkg, date_osm, round(time.perf_counter() - t0, 1))
