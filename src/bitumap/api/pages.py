"""Pages HTML rendues côté serveur : accueil, données personnelles (FR-027), à propos et
mentions légales (issue #57)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

from bitumap.api.application import chemin_local, gabarits
from bitumap.api.auth import session_courante
from bitumap.config import reglages

routeur = APIRouter()


@routeur.get("/")
def accueil(requete: Request) -> Response:
    session = session_courante(requete)
    return gabarits.TemplateResponse(
        requete,
        "accueil.html",
        {
            "session": session,
            "compte_supprime": requete.query_params.get("compte") == "supprime",
            "session_expiree": session is None and requete.query_params.get("motif") == "session",
            "suite": chemin_local(requete.query_params.get("suite")),
        },
    )


@routeur.get("/confidentialite")
def confidentialite(requete: Request) -> Response:
    return gabarits.TemplateResponse(
        requete,
        "confidentialite.html",
        {"session": session_courante(requete), "contact": reglages().email_mainteneur},
    )


def _editeur() -> dict[str, str | None]:
    """Identité de l'éditeur, fournie par la configuration (jamais versionnée)."""
    r = reglages()
    champs = ("nom", "forme", "responsable", "siret", "adresse", "contact", "site", "presentation")
    return {c: getattr(r, f"editeur_{c}") for c in champs}


@routeur.get("/a-propos")
def a_propos(requete: Request) -> Response:
    return gabarits.TemplateResponse(
        requete, "a_propos.html", {"session": session_courante(requete), "editeur": _editeur()}
    )


@routeur.get("/mentions-legales")
def mentions_legales(requete: Request) -> Response:
    return gabarits.TemplateResponse(
        requete,
        "mentions_legales.html",
        {"session": session_courante(requete), "editeur": _editeur()},
    )
