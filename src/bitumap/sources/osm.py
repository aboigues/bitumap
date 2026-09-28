"""OpenStreetMap (ODbL) : itinéraires de bus, feux, giratoires, revêtement, ouvrages d'art.

Portée régionale (FR-007b) : une passe sur l'extrait Geofabrik Île-de-France (≈ 3 min,
≈ 600 Mo de mémoire) produit un fichier compact mis en cache ; chaque commune n'en lit
ensuite que son emprise.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import osmium
from shapely.geometry import LineString, Point

from bitumap.sources.base import Extraction, Provenance, SourceIndisponible, client_http

URL_EXTRAIT = "https://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf"
LICENCE = "ODbL (© contributeurs OpenStreetMap)"
_DATE_FICHIER = re.compile(r"-(\d{6})\.osm\.pbf$")
SURFACES_RIGIDES = {
    "concrete",
    "concrete:plates",
    "concrete:lanes",
    "paving_stones",
    "sett",
    "cobblestone",
    "unhewn_cobblestone",
}


@dataclass(frozen=True)
class DonneesOsm:
    """Couches GeoDataFrame en WGS 84."""

    voies_bus: (
        gpd.GeoDataFrame
    )  # way_id, lignes, nb_itineraires, nom, ref, highway, surface, pont, sens_unique
    feux: gpd.GeoDataFrame  # node_id, pieton
    giratoires: gpd.GeoDataFrame  # way_id, nom


def telecharger(dossier: Path) -> tuple[Path, date]:
    """Télécharge l'extrait daté (redirection Geofabrik) et vérifie son MD5."""
    dossier.mkdir(parents=True, exist_ok=True)
    with client_http(timeout=900) as client:
        tete = client.head(URL_EXTRAIT)
        url = str(tete.url)
        trouve = _DATE_FICHIER.search(url)
        if not trouve:
            raise SourceIndisponible("OSM", "extrait non daté")
        extraction = datetime.strptime(trouve.group(1), "%y%m%d").date()
        cible = dossier / f"idf-{trouve.group(1)}.osm.pbf"
        if not cible.exists():
            attendu = client.get(url + ".md5").text.split()[0]
            partiel = cible.with_suffix(".partiel")
            md5 = hashlib.md5(usedforsecurity=False)
            with client.stream("GET", url) as reponse, partiel.open("wb") as sortie:
                reponse.raise_for_status()
                for bloc in reponse.iter_bytes(1 << 20):
                    md5.update(bloc)
                    sortie.write(bloc)
            if md5.hexdigest() != attendu:
                partiel.unlink()
                raise SourceIndisponible("OSM", "somme de contrôle MD5 incorrecte")
            partiel.rename(cible)
    return cible, extraction


def extraire_region(pbf: Path) -> DonneesOsm:
    """Passe régionale : relations bus → tronçons parcourus, feux, giratoires."""
    lignes_par_voie: dict[int, set[str]] = {}
    itineraires_par_voie: dict[int, int] = {}
    filtre_bus = osmium.filter.TagFilter(("route", "bus"), ("route", "trolleybus"))
    for rel in osmium.FileProcessor(str(pbf), osmium.osm.RELATION).with_filter(filtre_bus):
        ref = rel.tags.get("ref", "") or rel.tags.get("name", "")
        for membre in rel.members:
            if membre.type == "w" and membre.role in ("", "forward", "backward"):
                lignes_par_voie.setdefault(membre.ref, set()).add(ref)
                itineraires_par_voie[membre.ref] = itineraires_par_voie.get(membre.ref, 0) + 1

    voies, feux, giratoires = [], [], []
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations():
        if obj.is_node():
            if obj.tags.get("highway") == "traffic_signals":
                feux.append(
                    {
                        "node_id": obj.id,
                        "pieton": est_feu_pieton(obj.tags),
                        "geometry": Point(obj.location.lon, obj.location.lat),
                    }
                )
            continue
        est_bus = obj.id in lignes_par_voie
        est_giratoire = obj.tags.get("junction") in ("roundabout", "circular")
        if not (est_bus or est_giratoire):
            continue
        try:
            coords = [(n.lon, n.lat) for n in obj.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(coords) < 2:
            continue
        geometrie = LineString(coords)
        if est_bus:
            voies.append(
                {
                    "way_id": obj.id,
                    "lignes": ";".join(sorted(lignes_par_voie[obj.id])),
                    "nb_itineraires": itineraires_par_voie[obj.id],
                    "nom": obj.tags.get("name", ""),
                    "ref": obj.tags.get("ref", ""),
                    "highway": obj.tags.get("highway", ""),
                    "surface": obj.tags.get("surface", ""),
                    "pont": obj.tags.get("bridge", "no") not in ("no", ""),
                    "sens_unique": obj.tags.get("oneway", "no") in ("yes", "1", "-1")
                    or est_giratoire,
                    "geometry": geometrie,
                }
            )
        if est_giratoire:
            giratoires.append(
                {"way_id": obj.id, "nom": obj.tags.get("name", ""), "geometry": geometrie}
            )
    crs = "EPSG:4326"
    return DonneesOsm(
        gpd.GeoDataFrame(voies, crs=crs),
        gpd.GeoDataFrame(feux, crs=crs),
        gpd.GeoDataFrame(giratoires, crs=crs),
    )


COUCHES = ("voies_bus", "feux", "giratoires")


def enregistrer(donnees: DonneesOsm, fichier: Path) -> None:
    for couche in COUCHES:
        getattr(donnees, couche).to_file(fichier, layer=couche, driver="GPKG")


def lire_emprise(fichier: Path, emprise: tuple[float, float, float, float]) -> DonneesOsm:
    """Lit seulement l'emprise (minx, miny, maxx, maxy) en WGS 84."""
    return DonneesOsm(*(gpd.read_file(fichier, layer=c, bbox=emprise) for c in COUCHES))


def extraction_communale(
    fichier_regional: Path, date_extraction: date, emprise: tuple[float, float, float, float]
) -> Extraction:
    return Extraction(
        Provenance(
            "OpenStreetMap (extrait Geofabrik Île-de-France)",
            LICENCE,
            "https://www.openstreetmap.org/copyright",
            date_extraction,
            "regionale",
        ),
        lire_emprise(fichier_regional, emprise),
    )


def est_feu_pieton(tags) -> bool:
    """Feu de traversée piétonne seule (pas un carrefour) : exclu des « feux » de la méthode."""
    return (
        tags.get("crossing") in ("traffic_signals", "signals")
        or tags.get("traffic_signals") in ("crossing_only", "pedestrian_crossing")
        or tags.get("crossing:signals") == "yes"
    )


def est_rigide(surface: str) -> bool:
    return surface in SURFACES_RIGIDES
