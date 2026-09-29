"""Compte de l'utilisateur : suppression à sa demande (FR-027).

La suppression retire le compte et, en cascade, ses sessions, ses liens de connexion validés
et ses rattachements aux demandes ; les liens encore non validés pour son adresse sont aussi
supprimés. Les demandes restent en file (un autre compte peut y être rattaché) et les
rapports produits ne contiennent aucune donnée personnelle.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from bitumap.api.application import ErreurPublique, gabarits
from bitumap.api.auth import SessionRequise, nom_cookie, verifier_csrf
from bitumap.config import reglages
from bitumap.db import connexion

routeur = APIRouter()

CONFIRMATION = "SUPPRIMER"


@routeur.get("/compte")
def compte(requete: Request, session: SessionRequise) -> Response:
    return gabarits.TemplateResponse(
        requete, "compte.html", {"session": session, "confirmation": CONFIRMATION}
    )


def supprimer_compte(compte_id: str, email: str) -> None:
    with connexion() as conn:
        conn.execute("DELETE FROM lien_connexion WHERE email = %s", (email,))
        conn.execute("DELETE FROM compte WHERE id = %s", (compte_id,))


@routeur.post("/compte/suppression")
def suppression(
    session: SessionRequise,
    csrf: Annotated[str, Form()] = "",
    confirmation: Annotated[str, Form()] = "",
) -> Response:
    verifier_csrf(session, csrf)
    if confirmation.strip().upper() != CONFIRMATION:
        raise ErreurPublique(
            400, "confirmation_requise", f"Saisissez {CONFIRMATION} pour confirmer."
        )
    supprimer_compte(session.compte_id, session.email)
    reponse = RedirectResponse("/?compte=supprime", status_code=303)
    reponse.delete_cookie(nom_cookie(), path="/", secure=reglages().cookies_securises)
    return reponse
