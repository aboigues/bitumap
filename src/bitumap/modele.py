"""Entités du rapport (data-model.md, contracts/report-bundle.md)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Provenance = Literal["mesure", "estime", "ia"]
Statut = Literal["evalue", "non_evalue", "a_confirmer"]


@dataclass
class Facteur:
    nom: str
    valeur: float | str | None
    effet: float  # multiplicateur appliqué au score (1.0 = neutre)
    provenance: Provenance = "mesure"
    statut: Statut = "evalue"
    explication: str = ""
    unite: str = ""
    visible: bool = True  # affiché dans la liste courte des facteurs marquants
    modele: str | None = None
    date: str | None = None


@dataclass
class Route:
    classement: str = "indetermine"
    gestionnaire: str | None = None
    numero: str | None = None
    statut: str = "indetermine"  # concordant, a_verifier, indetermine
    source: str = ""


@dataclass
class Point:
    id: str
    type: Literal["arret", "feu", "giratoire"]
    nom: str
    lon: float
    lat: float
    voie: str = ""
    bus_jour: float = 0.0
    pointe_h: float | None = None
    lignes: list[str] = field(default_factory=list)
    route: Route = field(default_factory=Route)
    direction: str | None = None  # terminus desservis depuis le quai (FR-030), arrêts seulement
    facteurs: list[Facteur] = field(default_factory=list)
    panoramax: dict | None = None
    score_brut: float = 0.0
    score: int = 0
    rang: int = 0
    priorite: str = ""
    groupe: str = ""  # P1a, P1b, P1c (tiers des P1 par rang, méthode 1.1), P2 ou P3

    @property
    def libelle_type(self) -> str:
        return {"arret": "Arrêt de bus", "feu": "Carrefour à feux", "giratoire": "Giratoire"}[
            self.type
        ]

    def facteur(self, nom: str) -> Facteur | None:
        return next((f for f in self.facteurs if f.nom == nom), None)

    def en_dict(self) -> dict:
        from bitumap.facteurs.voirie import libelle
        from bitumap.points.direction import designation, identifiant
        from bitumap.score.methode import LIBELLES_GROUPES

        d = asdict(self)
        d["type_libelle"] = self.libelle_type
        d["route"]["libelle"] = libelle(self.route.classement)
        d["designation"] = designation(self)
        d["identifiant"] = identifiant(self)
        d["groupe_libelle"] = LIBELLES_GROUPES.get(self.groupe, self.groupe)
        return d
