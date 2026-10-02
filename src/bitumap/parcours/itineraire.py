"""Itinéraire de la Géoplateforme (006 R2, R4).

Service de l'IGN (BD TOPO, ressource ``bdtopo-osrm``, Licence Ouverte), hébergé en France,
sans clé ; profils ``car`` et ``pedestrian`` ; **15 points intermédiaires au plus** par
requête : un tracé plus long est découpé en tronçons enchaînés (la fin d'un tronçon est le
début du suivant). Débit : 5 requêtes par seconde et par adresse IP ; le limiteur en garde 4.
Nouvelles tentatives sur ``429`` et ``5xx`` (``sources.base.obtenir``).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import httpx

from bitumap.sources.base import Provenance, SourceIndisponible, obtenir

URL = "https://data.geopf.fr/navigation/itineraire"
RESSOURCE = "bdtopo-osrm"
MODES = {"voiture": "car", "pied": "pedestrian"}
MAX_INTERMEDIAIRES = 15
REQUETES_PAR_SECONDE = 4

Position = tuple[float, float]  # (lon, lat) en WGS 84


class Inaccessible(Exception):
    """Aucun itinéraire entre ces points dans le mode choisi."""


@dataclass
class Trajet:
    distance_m: float = 0.0
    duree_s: float = 0.0
    geometrie: list[list[float]] = field(default_factory=list)  # [[lon, lat], …]
    troncons: list[list[list[float]]] = field(default_factory=list)  # un tracé par requête
    etapes: list[tuple[float, float]] = field(default_factory=list)  # (m, s) par étape


class Limiteur:
    """Au plus ``par_seconde`` requêtes par seconde, partagé par les appels d'un processus."""

    def __init__(
        self,
        par_seconde: int = REQUETES_PAR_SECONDE,
        horloge: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self._intervalle = 1.0 / par_seconde
        self._horloge, self._dormir = horloge, dormir
        self._prochaine = 0.0
        self._verrou = threading.Lock()

    def attendre(self) -> None:
        with self._verrou:
            maintenant = self._horloge()
            if self._prochaine > maintenant:
                self._dormir(self._prochaine - maintenant)
                maintenant = self._prochaine
            self._prochaine = maintenant + self._intervalle


LIMITEUR = Limiteur()


def provenance() -> Provenance:
    return Provenance(
        "IGN Géoplateforme : itinéraire (BD TOPO)",
        "Licence Ouverte Etalab 2.0",
        "https://geoservices.ign.fr/services-geoplateforme-itineraire",
        date.today(),
        "communale",
    )


def _texte(p: Position) -> str:
    return f"{p[0]:.6f},{p[1]:.6f}"


def _appel(points: list[Position], mode: str, client: httpx.Client, limiteur: Limiteur) -> dict:
    params = {
        "resource": RESSOURCE,
        "profile": MODES[mode],
        "optimization": "fastest",
        "start": _texte(points[0]),
        "end": _texte(points[-1]),
        "geometryFormat": "geojson",
        "getSteps": "false",
        "getBbox": "false",
        "distanceUnit": "meter",
        "timeUnit": "second",
    }
    if len(points) > 2:
        params["intermediates"] = "|".join(_texte(p) for p in points[1:-1])
    limiteur.attendre()
    try:
        return obtenir(client, "Itinéraire IGN", URL, params=params).json()
    except SourceIndisponible as erreur:
        # 400 : points valides mais aucun itinéraire (point isolé dans ce mode).
        if str(erreur).endswith("HTTP 400"):
            raise Inaccessible from erreur
        raise


def trajet(
    points: list[Position], mode: str, client: httpx.Client, limiteur: Limiteur | None = None
) -> Trajet:
    """Trajet passant par ``points`` dans l'ordre (le premier et le dernier compris) ;
    limiteur du processus par défaut."""
    limiteur = limiteur or LIMITEUR
    if len(points) < 2:
        raise ValueError("au moins deux points")
    taille = MAX_INTERMEDIAIRES + 2
    resultat = Trajet()
    debut = 0
    while debut < len(points) - 1:
        morceau = points[debut : debut + taille]
        r = _appel(morceau, mode, client, limiteur)
        coordonnees = [list(c) for c in r["geometry"]["coordinates"]]
        resultat.troncons.append(coordonnees)
        resultat.geometrie += coordonnees if not resultat.geometrie else coordonnees[1:]
        resultat.distance_m += float(r["distance"])
        resultat.duree_s += float(r["duration"])
        resultat.etapes += [(float(p["distance"]), float(p["duration"])) for p in r["portions"]]
        debut += len(morceau) - 1
    return resultat
