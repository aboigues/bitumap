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

    def en_dict(self) -> dict[str, str]:
        return {
            "nom": self.nom,
            "licence": self.licence,
            "url": self.url,
            "date_extraction": self.date_extraction.isoformat(),
            "portee": self.portee,
        }


@dataclass
class Extraction:
    provenance: Provenance
    donnees: Any
    avertissements: list[str] = field(default_factory=list)


def client_http(timeout: float = 30) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


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
