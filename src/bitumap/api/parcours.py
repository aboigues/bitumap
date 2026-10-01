"""Parcours de surveillance (006, contracts/http-api.md) : formulaire, calcul, résultat, GPX.

Session obligatoire ; CSRF sur le calcul ; quota de 20 parcours par compte et par jour
(FR-013) ; résultat visible du seul compte qui l'a demandé (``404`` sinon). L'adresse de
départ n'est jamais journalisée (FR-012). Aucun script en ligne : le choix d'adresse se fait
par le formulaire, le serveur géocode.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from bitumap.api import quotas
from bitumap.api.application import ErreurPublique, gabarits
from bitumap.api.auth import SessionRequise, verifier_csrf
from bitumap.config import reglages
from bitumap.parcours import geocodage, gpx, service
from bitumap.score.methode import LIBELLES_GROUPES
from bitumap.sources.base import SourceIndisponible, client_http

routeur = APIRouter(prefix="/parcours")
_INSEE = re.compile(r"^\d{5}$")
QUOTA_PARCOURS = 20
MODES = {"voiture": "en voiture", "pied": "à pied"}


def _insee(insee: str) -> str:
    if not _INSEE.match(insee):
        raise ErreurPublique(404, "rapport_absent", "Rapport introuvable.")
    return insee


def _rapport(insee: str):
    try:
        return service.rapport(_insee(insee))
    except service.ErreurParcours as e:
        raise ErreurPublique(e.statut, e.code, e.message) from e


def _duree_texte(secondes: float) -> str:
    minutes = round(secondes / 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def _km_texte(metres: float) -> str:
    return f"{metres / 1000:.1f}".replace(".", ",") + " km"


gabarits.env.filters["duree"] = _duree_texte
gabarits.env.filters["km"] = _km_texte
gabarits.env.globals["libelles_groupes"] = LIBELLES_GROUPES


def _formulaire(requete, session, insee, r, valeurs=None, propositions=None, erreur=None):
    effectifs = Counter(p.groupe for p in r.points.values())
    return gabarits.TemplateResponse(
        requete,
        "parcours/formulaire.html",
        {
            "session": session,
            "insee": insee,
            "commune": service.nom_commune(insee, r.empreinte),
            "effectifs": {g: effectifs.get(g, 0) for g in service.NIVEAUX},
            "modes": MODES,
            "valeurs": valeurs
            or {"niveaux": ["P1a", "P1b"], "mode": "voiture", "duree_max_min": 180, "arret_min": 5},
            "propositions": propositions or [],
            "erreur": erreur,
        },
        status_code=400 if erreur else 200,
    )


@routeur.get("/adresses")
def adresses(session: SessionRequise, q: str = "", insee: str = "") -> JSONResponse:
    autour = service.centre(_rapport(insee)) if insee else None
    try:
        with client_http(timeout=20) as client:
            trouvees = geocodage.rechercher(q, client, autour=autour)
    except geocodage.TexteTropCourt as e:
        raise ErreurPublique(400, "texte_trop_court", "Saisissez au moins 3 caractères.") from e
    except SourceIndisponible as e:
        raise ErreurPublique(
            503, "geocodage_indisponible", "Recherche d'adresse indisponible."
        ) from e
    return JSONResponse(
        [{"libelle": a.libelle, "lon": a.lon, "lat": a.lat, "score": a.score} for a in trouvees],
        headers={"Cache-Control": "no-store"},
    )


@routeur.get("/resultat/{ident}.gpx")
def telecharger_gpx(ident: str, session: SessionRequise) -> Response:
    parcours = service.lire(ident, session.compte_id)
    if parcours is None:
        raise ErreurPublique(404, "parcours_inconnu", "Parcours introuvable ou expiré.")
    commune = service.nom_commune(parcours["commune_insee"], parcours["empreinte"])
    date = parcours["cree_le"].date().isoformat()
    return Response(
        gpx.produire(parcours, commune, reglages().url_publique),
        media_type="application/gpx+xml",
        headers={
            "Content-Disposition": (
                f'attachment; filename="parcours-{parcours["commune_insee"]}-{date}.gpx"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


@routeur.get("/resultat/{ident}")
def resultat(requete: Request, ident: str, session: SessionRequise) -> Response:
    parcours = service.lire(ident, session.compte_id)
    if parcours is None:
        raise ErreurPublique(404, "parcours_inconnu", "Parcours introuvable ou expiré.")
    return gabarits.TemplateResponse(
        requete,
        "parcours/resultat.html",
        {
            "session": session,
            "parcours": parcours,
            "r": parcours["resultat"],
            "commune": service.nom_commune(parcours["commune_insee"], parcours["empreinte"]),
            "modes": MODES,
        },
        headers={"Cache-Control": "private, no-store"},
    )


@routeur.get("/{insee}")
def formulaire(requete: Request, insee: str, session: SessionRequise) -> Response:
    return _formulaire(requete, session, insee, _rapport(insee))


@routeur.post("/{insee}")
def calculer(
    requete: Request,
    insee: str,
    session: SessionRequise,
    csrf: Annotated[str, Form()] = "",
    adresse: Annotated[str, Form(max_length=300)] = "",
    choix: Annotated[int | None, Form()] = None,
    niveaux: Annotated[list[str], Form()] = [],  # noqa: B006 (valeur par défaut de FastAPI)
    mode: Annotated[str, Form()] = "voiture",
    duree_max_min: Annotated[int, Form()] = 180,
    arret_min: Annotated[int, Form()] = 5,
) -> Response:
    verifier_csrf(session, csrf)
    r = _rapport(insee)
    valeurs = {
        "adresse": adresse,
        "niveaux": niveaux,
        "mode": mode,
        "duree_max_min": duree_max_min,
        "arret_min": arret_min,
    }
    if (
        not niveaux
        or not set(niveaux) <= set(service.NIVEAUX)
        or mode not in MODES
        or not 30 <= duree_max_min <= 480
        or not 0 <= arret_min <= 30
    ):
        raise ErreurPublique(400, "parametres_invalides", "Paramètres du parcours invalides.")
    try:
        with client_http(timeout=20) as client:
            trouvees = geocodage.rechercher(adresse, client, autour=service.centre(r))
    except geocodage.TexteTropCourt:
        return _formulaire(
            requete, session, insee, r, valeurs, erreur="Saisissez l'adresse de départ."
        )
    except SourceIndisponible as e:
        raise ErreurPublique(
            503, "geocodage_indisponible", "Recherche d'adresse indisponible : réessayez."
        ) from e
    if choix is not None and 0 <= choix < len(trouvees):
        depart = trouvees[choix]
    else:
        depart = geocodage.choix_automatique(trouvees)
    if depart is None:
        message = (
            "Précisez l'adresse de départ : plusieurs adresses correspondent."
            if trouvees
            else "Adresse introuvable : vérifiez la saisie."
        )
        return _formulaire(requete, session, insee, r, valeurs, trouvees, message)
    quotas.limiter(
        f"parcours:compte:{session.compte_id}",
        timedelta(days=1),
        QUOTA_PARCOURS,
        "quota_parcours",
        "Limite de parcours du jour atteinte : réessayez demain.",
    )
    try:
        ident = service.calculer(
            insee, session.compte_id, depart, niveaux, mode, duree_max_min, arret_min
        )
    except service.ErreurParcours as e:
        raise ErreurPublique(e.statut, e.code, e.message) from e
    return RedirectResponse(f"/parcours/resultat/{ident}", status_code=303)
