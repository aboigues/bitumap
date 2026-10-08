"""Menu commun et fil d'Ariane (008, contracts/interface.md).

Un seul jeu d'entrées, rendu par ``_menu.html`` dans les pages et dans le rapport.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bitumap.api.application import gabarits
from bitumap.api.auth import Session, est_mainteneur
from bitumap.territoire import metadonnees

Visibilite = Literal["tous", "connecte", "mainteneur", "visiteur"]
Fil = list[tuple[str, str | None]]  # (libellé, adresse) ; le dernier élément sans adresse


@dataclass(frozen=True)
class Entree:
    rubrique: str
    libelle: str
    adresse: str
    visible: Visibilite


ENTREES = (
    Entree("accueil", "Accueil", "/", "tous"),
    Entree("demandes", "Mes demandes", "/demandes", "connecte"),
    Entree("terrain", "Relevés terrain", "/terrain", "connecte"),
    Entree("parcours", "Parcours", "/parcours", "connecte"),
    Entree("compte", "Mon compte", "/compte", "connecte"),
    Entree("moderation", "Modération", "/terrain/moderation", "mainteneur"),
    Entree("confidentialite", "Données personnelles", "/confidentialite", "visiteur"),
)


def menu(session: Session | None) -> list[Entree]:
    """Entrées visibles par ce compte ; « Modération » pour le seul mainteneur (FR-013)."""
    if session is None:
        return [e for e in ENTREES if e.visible in ("tous", "visiteur")]
    mainteneur = est_mainteneur(session)
    return [
        e
        for e in ENTREES
        if e.visible in ("tous", "connecte") or (e.visible == "mainteneur" and mainteneur)
    ]


def fil(*elements: tuple[str, str | None]) -> Fil:
    """Fil d'Ariane commençant par l'accueil ; le dernier élément est la page courante."""
    return [("Accueil", "/"), *elements]


gabarits.env.globals["menu"] = menu
gabarits.env.globals["metadonnees_communes"] = metadonnees
