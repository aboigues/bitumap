"""Export des relevés d'une commune (003 US4 : FR-013, FR-014 ; contracts/http-api.md).

- CSV pour les tableurs : UTF-8 avec BOM, séparateur ``;``, une ligne par relevé visible
  (dernière version) ; texte libre neutralisé contre l'injection de formules.
- GeoJSON (WGS 84) aux mêmes champs, pour les logiciels de cartographie.
- Échantillon de réfection au format de ``bitumap.ia.evaluer`` (002 T072, T073).

Niveau estimé et position : ceux du rapport **en vigueur** ; à défaut (point sorti du
rapport), position du téléphone. Liens de photos seulement pour les relevés du lecteur.
"""

from __future__ import annotations

import csv
import io

from bitumap.config import reglages
from bitumap.score.methode import LIBELLES_GROUPES
from bitumap.terrain import depot
from bitumap.terrain.points import PointRapport

COLONNES = (
    "releve",
    "point",
    "designation",
    "lon",
    "lat",
    "niveau_estime",
    "niveau_constate",
    "profondeur_mm",
    "instrument",
    "annee_refection",
    "source_refection",
    "observation",
    "date",
    "version",
    "auteur",
    "nb_photos",
    "photos",
)
SOURCES_FIABLES = ("constatee", "services_techniques")
_DEBUTS_DE_FORMULE = ("=", "+", "-", "@", "\t", "\r")


def _lien_photo(photo_id: str) -> str:
    return f"{reglages().url_publique.rstrip('/')}/terrain/photos/{photo_id}"


def lignes(commune_insee: str, lecteur_id: str, points: dict[str, PointRapport]) -> list[dict]:
    resultat = []
    for r in depot.releves_visibles(commune_insee, lecteur_id):
        point = points.get(r["point_id"])
        lon, lat = (point.lon, point.lat) if point else (r["lon"], r["lat"])
        resultat.append(
            {
                "releve": r["id"],
                "point": r["point_id"],
                "designation": point.designation if point else r["point_designation"],
                "lon": lon,
                "lat": lat,
                "niveau_estime": LIBELLES_GROUPES.get(point.groupe, point.groupe) if point else "",
                "niveau_constate": depot.LIBELLES_NIVEAUX[r["niveau"]],
                "profondeur_mm": r["profondeur_mm"],
                "instrument": r["instrument"],
                "annee_refection": r["annee_refection"],
                "source_refection": depot.LIBELLES_SOURCES.get(r["source_refection"], ""),
                "observation": r["observation"],
                "date": r["cree_le"],
                "version": r["version"],
                "auteur": r["auteur"],
                "nb_photos": r["nb_photos"],
                "photos": [_lien_photo(p) for p in r["photos"]],
            }
        )
    return resultat


def _cellule(valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, list):
        valeur = " ".join(valeur)
    texte = str(valeur)
    # Injection de formules (OWASP « CSV injection ») : un texte libre commençant par « = »
    # serait exécuté par le tableur ; l'apostrophe le fait lire comme du texte.
    if isinstance(valeur, str) and texte.startswith(_DEBUTS_DE_FORMULE):
        return "'" + texte
    return texte


def en_csv(donnees: list[dict]) -> bytes:
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(COLONNES)
    for ligne in donnees:
        ecrivain.writerow([_cellule(ligne[c]) for c in COLONNES])
    return tampon.getvalue().encode("utf-8-sig")


def en_geojson(donnees: list[dict]) -> dict:
    entites = []
    for ligne in donnees:
        proprietes = {c: ligne[c] for c in COLONNES if c not in ("lon", "lat")}
        geometrie = (
            {"type": "Point", "coordinates": [ligne["lon"], ligne["lat"]]}
            if ligne["lon"] is not None
            else None
        )
        entites.append({"type": "Feature", "geometry": geometrie, "properties": proprietes})
    return {"type": "FeatureCollection", "features": entites}


def echantillon_refection(commune_insee: str, points: dict[str, PointRapport]) -> dict:
    """Points du rapport en vigueur dont l'année de réfection vient d'une source fiable ;
    pour chaque point, le relevé le plus récent qui la renseigne."""
    retenus: dict[str, dict] = {}
    for r in depot.releves_visibles(commune_insee, None):  # du plus récent au plus ancien
        point = points.get(r["point_id"])
        if point is None or r["point_id"] in retenus:
            continue
        if r["annee_refection"] is None or r["source_refection"] not in SOURCES_FIABLES:
            continue
        retenus[r["point_id"]] = {
            "id": point.id,
            "nom": point.nom,
            "lon": point.lon,
            "lat": point.lat,
            "refection_annee": r["annee_refection"],
            "source": r["source_refection"],
            "groupe": point.groupe,
        }
    return {"points": sorted(retenus.values(), key=lambda p: p["id"])}
