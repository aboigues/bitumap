"""Socle des adaptateurs de sources (constitution, principes III et VII).

Chaque extraction porte sa licence, son URL et sa date ; le client HTTP est partagé (délai
maximal, nouvelles tentatives bornées, User-Agent explicite).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
import numpy as np

USER_AGENT = "bitumap (+https://github.com/aboigues/bitumap)"


class SourceIndisponible(Exception):
    """La source n'a pas pu être lue après les nouvelles tentatives."""

    def __init__(self, source: str, detail: str):
        super().__init__(f"{source} : {detail}")
        self.source = source


@dataclass(frozen=True)
class Provenance:
    """Métadonnées affichées dans la section « Sources » du rapport."""

    nom: str
    licence: str
    url: str
    date_extraction: date
    portee: str  # « regionale » ou « communale »
    # Service hors de l'UE, déclaré dans le rapport (constitution, principe III ; 004 R3)
    hors_ue: bool = False

    def en_dict(self) -> dict[str, str | bool]:
        d: dict[str, str | bool] = {
            "nom": self.nom,
            "licence": self.licence,
            "url": self.url,
            "date_extraction": self.date_extraction.isoformat(),
            "portee": self.portee,
        }
        if self.hors_ue:
            d["hors_ue"] = True
        return d


@dataclass
class Hauteurs:
    """Modèles LiDAR HD autour d'un point (004 R1) : altitudes en mètres (IGN69), grilles
    nord en haut ; ``origine`` = coin nord-ouest en Lambert 93 ; nodata = NaN."""

    mns: np.ndarray
    mnt: np.ndarray
    origine: tuple[float, float]
    resolution: float
    millesime: str  # « code_mission date de fin d'acquisition » (index des dalles)


@dataclass
class Raster:
    """Grille géoréférencée (température de surface, 004 R3) ; NaN = pas de mesure."""

    valeurs: np.ndarray
    transform: tuple[float, float, float, float, float, float]  # ordre GDAL
    crs: str
    ete: int


@dataclass
class Extraction:
    provenance: Provenance
    donnees: Any
    avertissements: list[str] = field(default_factory=list)


def client_http(timeout: float = 30) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def cause(erreur: Exception) -> str:
    """Cause lisible d'un échec, pour le rapport : détail de la source (« Orthophotos IGN :
    HTTP 429 ») ou, à défaut, type de l'exception (jamais son message, qui peut contenir une
    adresse ou une clé)."""
    return str(erreur) if isinstance(erreur, SourceIndisponible) else type(erreur).__name__


def obtenir(
    client: httpx.Client, source: str, url: str, *, tentatives: int = 3, **kwargs
) -> httpx.Response:
    """GET avec nouvelles tentatives bornées (erreurs réseau et réponses 5xx/429)."""
    derniere = "inconnue"
    for essai in range(tentatives):
        try:
            reponse = client.get(url, **kwargs)
            if reponse.status_code < 500 and reponse.status_code != 429:
                reponse.raise_for_status()
                return reponse
            derniere = f"HTTP {reponse.status_code}"
        except httpx.HTTPStatusError as erreur:
            raise SourceIndisponible(source, f"HTTP {erreur.response.status_code}") from erreur
        except httpx.TransportError as erreur:
            derniere = type(erreur).__name__
        time.sleep(min(2**essai, 8))
    raise SourceIndisponible(source, derniere)


def verifier_url(source: str, url: str, hotes: tuple[str, ...]) -> str:
    """URL lue dans la réponse d'un service tiers (lien de fichier, ressource d'un jeu) :
    HTTPS et hôte attendu, sinon refusée. Évite d'aller chercher une adresse imposée par une
    réponse altérée (fichier local, service interne)."""
    try:
        lue = httpx.URL(url)
    except (httpx.InvalidURL, TypeError) as erreur:
        raise SourceIndisponible(source, "URL invalide") from erreur
    if lue.scheme != "https" or lue.host not in hotes:
        raise SourceIndisponible(source, f"URL refusée ({lue.scheme}://{lue.host})")
    return url


def telecharger(
    client: httpx.Client, source: str, url: str, max_octets: int, *, tentatives: int = 3
) -> bytes:
    """GET d'un fichier, taille bornée (annoncée et réelle), nouvelles tentatives comme
    ``obtenir``."""
    derniere = "inconnue"
    for essai in range(tentatives):
        try:
            with client.stream("GET", url) as reponse:
                if reponse.status_code >= 500 or reponse.status_code == 429:
                    derniere = f"HTTP {reponse.status_code}"
                else:
                    reponse.raise_for_status()
                    annonce = int(reponse.headers.get("content-length") or 0)
                    if annonce > max_octets:
                        raise SourceIndisponible(source, f"fichier trop lourd ({annonce} octets)")
                    morceaux, total = [], 0
                    for morceau in reponse.iter_bytes():
                        total += len(morceau)
                        if total > max_octets:
                            raise SourceIndisponible(source, f"fichier trop lourd (> {max_octets})")
                        morceaux.append(morceau)
                    return b"".join(morceaux)
        except httpx.HTTPStatusError as erreur:
            raise SourceIndisponible(source, f"HTTP {erreur.response.status_code}") from erreur
        except httpx.TransportError as erreur:
            derniere = type(erreur).__name__
        time.sleep(min(2**essai, 8))
    raise SourceIndisponible(source, derniere)
