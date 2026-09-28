"""Code postal → communes, via l'API Géo (geo.api.gouv.fr, Licence Ouverte).

Paris est traitée par arrondissement (research R6) : ``750xx`` → arrondissement ``751xx``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

URL_API_GEO = "https://geo.api.gouv.fr"
DEPARTEMENTS_IDF = frozenset({"75", "77", "78", "91", "92", "93", "94", "95"})
USER_AGENT = "bitumap (+https://github.com/aboigues/bitumap)"
_FORMAT = re.compile(r"^\d{5}$")
_INSEE = re.compile(r"^(\d{5}|2[AB]\d{3})$")


class ErreurTerritoire(Exception):
    """Erreur présentable à l'utilisateur ; ``code`` suit contracts/http-api.md."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Commune:
    insee: str
    nom: str
    departement: str


def _client() -> httpx.Client:
    return httpx.Client(base_url=URL_API_GEO, timeout=10, headers={"User-Agent": USER_AGENT})


def valider_format(code_postal: str) -> str:
    """Vérifie le format et le périmètre sans aucun appel externe (FR-001, FR-002)."""
    code = (code_postal or "").strip()
    if not _FORMAT.match(code):
        raise ErreurTerritoire("format_invalide", "Un code postal comporte 5 chiffres.")
    if code[:2] not in DEPARTEMENTS_IDF:
        raise ErreurTerritoire(
            "hors_ile_de_france",
            "Le service couvre uniquement l'Île-de-France (75, 77, 78, 91, 92, 93, 94, 95).",
        )
    return code


def communes_du_code_postal(code_postal: str) -> list[Commune]:
    """Communes d'Île-de-France couvertes par le code postal (arrondissements pour Paris)."""
    code = valider_format(code_postal)
    parametres = {"codePostal": code, "fields": "nom,code,codeDepartement"}
    if code.startswith("75"):
        parametres["type"] = "arrondissement-municipal"
    with _client() as client:
        reponse = client.get("/communes", params=parametres)
        reponse.raise_for_status()
        donnees = reponse.json()
    communes = sorted(
        (
            Commune(insee=c["code"], nom=c["nom"], departement=c["codeDepartement"])
            for c in donnees
            if c.get("codeDepartement") in DEPARTEMENTS_IDF
        ),
        key=lambda c: c.nom,
    )
    if not communes:
        raise ErreurTerritoire("code_inexistant", "Ce code postal n'existe pas.")
    return communes


def commune_par_insee(insee: str) -> Commune:
    """Commune ou arrondissement d'Île-de-France à partir de son code INSEE."""
    if not _INSEE.match(insee or ""):
        raise ErreurTerritoire("commune_invalide", "Commune inconnue.")
    chemin = f"/communes/{insee}"
    parametres = {"fields": "nom,code,codeDepartement"}
    if insee.startswith("751"):
        parametres["type"] = "arrondissement-municipal"
    with _client() as client:
        reponse = client.get(chemin, params=parametres)
        if reponse.status_code == 404:
            raise ErreurTerritoire("commune_invalide", "Commune inconnue.")
        reponse.raise_for_status()
        c = reponse.json()
    if c.get("codeDepartement") not in DEPARTEMENTS_IDF:
        raise ErreurTerritoire("commune_invalide", "Commune hors Île-de-France.")
    return Commune(insee=c["code"], nom=c["nom"], departement=c["codeDepartement"])


def contour_geojson(insee: str) -> dict:
    """Contour communal (GeoJSON, WGS 84)."""
    parametres = {"format": "geojson", "geometry": "contour"}
    if insee.startswith("751"):
        parametres["type"] = "arrondissement-municipal"
    with _client() as client:
        reponse = client.get(f"/communes/{insee}", params=parametres)
        reponse.raise_for_status()
        return reponse.json()
