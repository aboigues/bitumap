"""IDFM : offre de bus par arrêt (Licence Ouverte v2.0).

Formules retrouvées sur le prototype (vérifiées sur 3 arrêts de Courbevoie) :

- ``bus_jour`` : passages par jour, moyenne hebdomadaire hors vacances (somme des 7 jours / 7) ;
- ``pointe_h`` : maximum horaire d'un jour de semaine moyen (lundi à vendredi / 5).

Portée : communale (filtre ``code_commune``), plus légère que l'export régional de 1,3 M
lignes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import httpx

from bitumap.sources.base import Extraction, Provenance, client_http, obtenir

JEU = "offre_hebdomadaire_moyenne_hors_vacances"
URL = f"https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/{JEU}"
LICENCE = "Licence Ouverte v2.0 (Etalab)"
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


@dataclass
class ArretOffre:
    id_arret: str
    nom: str
    lat: float
    lon: float
    bus_jour: float = 0.0
    pointe_h: float = 0.0
    par_ligne_jour: dict[str, float] = field(default_factory=dict)

    @property
    def lignes(self) -> list[str]:
        return sorted(self.par_ligne_jour, key=lambda x: (not x[:1].isdigit(), x.zfill(6)))


def agreger(lignes: list[dict]) -> dict[str, ArretOffre]:
    """Agrège les lignes brutes de l'offre (mode Bus uniquement) par arrêt."""
    arrets: dict[str, ArretOffre] = {}
    par_heure: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for r in lignes:
        if r.get("libelle_mode_ligne") != "Bus":
            continue
        ident = str(r["id_arret"])
        arret = arrets.get(ident)
        if arret is None:
            arret = arrets[ident] = ArretOffre(
                ident, r["nom_arret"], float(r["latitude_arret"]), float(r["longitude_arret"])
            )
        hebdo = sum(float(r[f"nb_courses_{j}"] or 0) for j in JOURS) / 7
        semaine = sum(float(r[f"nb_courses_{j}"] or 0) for j in JOURS[:5]) / 5
        ligne = str(r["nom_ligne_commerciale"])
        arret.bus_jour += hebdo
        arret.par_ligne_jour[ligne] = arret.par_ligne_jour.get(ligne, 0.0) + hebdo
        par_heure[ident][int(r["tranche_horaire"])] += semaine
    for ident, arret in arrets.items():
        arret.pointe_h = max(par_heure[ident].values(), default=0.0)
    return arrets


# L'offre IDFM rattache tout Paris à la commune 75056 : un arrondissement (751xx) n'y figure
# pas. Les arrêts sont ensuite gardés par le contour de l'arrondissement (points.arrets).
PARIS = "75056"


def code_commune_offre(insee: str) -> str:
    return PARIS if insee.startswith("751") else insee


def date_mise_a_jour(client: httpx.Client) -> date:
    meta = obtenir(client, "IDFM", URL).json()
    return date.fromisoformat(meta["metas"]["default"]["modified"][:10])


def acquerir(insee: str, client: httpx.Client | None = None) -> Extraction:
    fermer = client is None
    client = client or client_http(timeout=120)
    try:
        maj = date_mise_a_jour(client)
        lignes = obtenir(
            client,
            "IDFM",
            f"{URL}/exports/json",
            params={
                "where": f'code_commune="{code_commune_offre(insee)}" AND libelle_mode_ligne="Bus"'
            },
        ).json()
    finally:
        if fermer:
            client.close()
    return Extraction(
        Provenance(
            "IDFM : offre hebdomadaire moyenne hors vacances", LICENCE, URL, maj, "communale"
        ),
        agreger(lignes),
    )
