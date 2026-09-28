"""Pages HTML rendues côté serveur (US1 : accueil ; complétées dans les tâches suivantes)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

from bitumap.api.application import gabarits
from bitumap.api.auth import session_courante

routeur = APIRouter()


@routeur.get("/")
def accueil(requete: Request) -> Response:
    session = session_courante(requete)
    return gabarits.TemplateResponse(requete, "accueil.html", {"session": session})
