"""Pages HTML rendues côté serveur : accueil, données personnelles (FR-027)."""

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
