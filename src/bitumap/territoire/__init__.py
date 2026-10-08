"""Territoire : communes d'Île-de-France par code postal (002) ou par nom (008)."""

from bitumap.territoire.api_geo import (
    Commune,
    ErreurTerritoire,
    commune_par_insee,
    communes_du_code_postal,
    valider_format,
)
from bitumap.territoire.recherche import metadonnees, par_insee, rechercher

__all__ = [
    "Commune",
    "ErreurTerritoire",
    "commune_par_insee",
    "communes_du_code_postal",
    "metadonnees",
    "par_insee",
    "rechercher",
    "valider_format",
]
