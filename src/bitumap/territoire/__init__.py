"""Territoire : code postal → communes d'Île-de-France (FR-001 à FR-003)."""

from bitumap.territoire.api_geo import (
    Commune,
    ErreurTerritoire,
    commune_par_insee,
    communes_du_code_postal,
    valider_format,
)

__all__ = [
    "Commune",
    "ErreurTerritoire",
    "commune_par_insee",
    "communes_du_code_postal",
    "valider_format",
]
