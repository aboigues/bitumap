"""Export GPX 1.1 d'un parcours (006 R5, FR-008, FR-012).

Bibliothèque standard seulement. Un point de passage « Départ », puis un par point visité dans
l'ordre, nommé « ordre · niveau · désignation » ; une trace avec un segment par tronçon
calculé ; métadonnées : commune, date et méthode du rapport, sources et licences. Aucune
donnée de compte ; l'adresse de départ n'y figure que comme point « Départ ».
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from bitumap.score.methode import LIBELLES_GROUPES

NS = "http://www.topografix.com/GPX/1/1"
SOURCES_RAPPORT = (
    "IDFM (offre de bus, ODbL / Licence Mobilités)",
    "OpenStreetMap (ODbL)",
    "IGN Géoplateforme (BD TOPO, géocodage, itinéraire ; Licence Ouverte Etalab 2.0)",
)


def _el(parent, nom: str, texte: str | None = None, **attributs) -> ET.Element:
    e = ET.SubElement(parent, f"{{{NS}}}{nom}", {k: str(v) for k, v in attributs.items()})
    if texte is not None:
        e.text = texte
    return e


def _coord(valeur: float) -> str:
    return f"{valeur:.6f}"


def nom_point(visite: dict) -> str:
    niveau = LIBELLES_GROUPES.get(visite["niveau"], visite["niveau"])
    return f"{visite['ordre']} · {niveau} · {visite['designation']}"


def produire(parcours: dict, commune: str, url_publique: str, version_methode: str = "") -> bytes:
    """GPX d'une ligne de la table ``parcours``."""
    ET.register_namespace("", NS)
    resultat, resume = parcours["resultat"], parcours["resultat"]["resume"]
    racine = ET.Element(f"{{{NS}}}gpx", {"version": "1.1", "creator": "bitumap"})
    meta = _el(racine, "metadata")
    _el(meta, "name", f"Parcours de surveillance — {commune}")
    _el(
        meta,
        "desc",
        f"Rapport du {resume['rapport_date']}"
        + (f", méthode {version_methode}" if version_methode else "")
        + f". {resume['nb_visites']} points dans l'ordre du rang. Sources : "
        + " ; ".join(SOURCES_RAPPORT)
        + ".",
    )
    _el(meta, "time", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    depart = _el(
        racine, "wpt", lat=_coord(parcours["depart_lat"]), lon=_coord(parcours["depart_lon"])
    )
    _el(depart, "name", "Départ")
    lien_rapport = (
        f"{url_publique.rstrip('/')}/rapports/{parcours['commune_insee']}/{parcours['empreinte']}"
    )
    for v in resultat["visites"]:
        wpt = _el(racine, "wpt", lat=_coord(v["lat"]), lon=_coord(v["lon"]))
        _el(wpt, "name", nom_point(v))
        _el(
            wpt,
            "desc",
            f"Rang {v['rang']} · {v['point_id']} · fiche : {lien_rapport}",
        )
    trk = _el(racine, "trk")
    _el(trk, "name", f"Boucle — {commune}")
    for troncon in resultat["troncons"]:
        segment = _el(trk, "trkseg")
        for lon, lat in troncon:
            _el(segment, "trkpt", lat=_coord(lat), lon=_coord(lon))
    return ET.tostring(racine, encoding="utf-8", xml_declaration=True)
