"""Adresse de départ : géocodage de la Géoplateforme (006 R1, FR-003).

Service de l'IGN (Base Adresse Nationale, Licence Ouverte), hébergé en France, sans clé.
L'adresse saisie n'est jamais écrite dans les journaux (FR-012).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from bitumap.sources.base import Provenance, obtenir

URL = "https://data.geopf.fr/geocodage/search"
LIMITE = 5
LONGUEUR_MIN = 3
SCORE_SUR = 0.7
ECART_AMBIGU = 0.1  # deux résultats à moins de 0,1 de score : l'agent choisit


class TexteTropCourt(ValueError):
    pass


@dataclass(frozen=True)
class Adresse:
    libelle: str
    lon: float
    lat: float
    score: float


def provenance() -> Provenance:
    return Provenance(
        "IGN Géoplateforme : géocodage (Base Adresse Nationale)",
        "Licence Ouverte Etalab 2.0",
        "https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage",
        date.today(),
        "communale",
    )


def rechercher(
    texte: str,
    client: httpx.Client,
    limite: int = LIMITE,
    autour: tuple[float, float] | None = None,
) -> list[Adresse]:
    """Adresses officielles correspondant au texte, de la plus probable à la moins probable ;
    ``autour`` (lon, lat) favorise les adresses proches de la commune."""
    texte = (texte or "").strip()
    if len(texte) < LONGUEUR_MIN:
        raise TexteTropCourt
    params = {"q": texte, "limit": limite, "index": "address"}
    if autour is not None:
        params |= {"lon": f"{autour[0]:.6f}", "lat": f"{autour[1]:.6f}"}
    entites = obtenir(client, "Géocodage IGN", URL, params=params).json().get("features", [])
    adresses = [
        Adresse(
            str(e["properties"]["label"]),
            float(e["geometry"]["coordinates"][0]),
            float(e["geometry"]["coordinates"][1]),
            float(e["properties"].get("score", 0.0)),
        )
        for e in entites
        if e.get("geometry") and e.get("properties", {}).get("label")
    ]
    return sorted(adresses, key=lambda a: -a.score)[:limite]


def choix_automatique(adresses: list[Adresse]) -> Adresse | None:
    """Adresse retenue sans demander à l'agent : sûre et sans concurrente proche."""
    if not adresses or adresses[0].score < SCORE_SUR:
        return None
    if len(adresses) > 1 and adresses[0].score - adresses[1].score < ECART_AMBIGU:
        return None
    return adresses[0]
