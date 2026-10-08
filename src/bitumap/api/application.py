"""Construction de l'application : en-têtes de sécurité, erreurs sans détail technique."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from bitumap import heure
from bitumap.config import reglages

journal = logging.getLogger("bitumap.api")

DOSSIER = Path(__file__).parent
gabarits = Jinja2Templates(directory=str(DOSSIER / "gabarits"))
gabarits.env.filters["heure"] = heure.formater  # heure de Paris (le serveur est en UTC)

EN_TETES_SECURITE = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


class ErreurPublique(Exception):
    """Erreur montrée à l'utilisateur : code stable + message sans détail technique."""

    def __init__(self, statut: int, code: str, message: str):
        super().__init__(message)
        self.statut = statut
        self.code = code
        self.message = message


def _veut_json(requete: Request) -> bool:
    return "application/json" in requete.headers.get("accept", "")


def chemin_local(valeur: str | None) -> str | None:
    """Chemin de ce site seulement (« /demandes?x=1 ») : jamais une autre origine
    (« //exemple », « /\\exemple », « /<tabulation>/exemple »), ni une page de connexion
    (boucle)."""
    if not valeur or len(valeur) > 512 or any(c.isspace() or c == "\\" for c in valeur):
        return None
    # Forme reconnue par CodeQL (py/url-redirection) : barres inverses ramenées à « / »,
    # puis ni schéma ni hôte.
    valeur = valeur.replace("\\", "/")
    morceaux = urlsplit(valeur)
    if (
        morceaux.scheme
        or morceaux.netloc
        or not valeur.startswith("/")
        or valeur.startswith(("//", "/connexion"))
    ):
        return None
    return valeur


def page_precedente(requete: Request) -> str | None:
    """Page d'où vient la requête, si elle est sur ce site (en-tête Referer)."""
    precedente = urlsplit(requete.headers.get("referer", ""))
    if precedente.netloc != requete.url.netloc:
        return None
    chemin = precedente.path + (f"?{precedente.query}" if precedente.query else "")
    return chemin_local(chemin)


def reponse_erreur(requete: Request, statut: int, code: str, message: str):
    if _veut_json(requete):
        return JSONResponse({"erreur": code, "message": message}, status_code=statut)
    if code == "connexion_requise":
        # Session expirée ou absente : connexion, puis retour à la page voulue (anomalie 3).
        voulue = requete.url.path + (f"?{requete.url.query}" if requete.url.query else "")
        suite = chemin_local(voulue) if requete.method == "GET" else page_precedente(requete)
        cible = "/?" + urlencode({"motif": "session", **({"suite": suite} if suite else {})})
        return RedirectResponse(cible, status_code=303)
    return gabarits.TemplateResponse(
        requete,
        "erreur.html",
        {"message": message, "code": code, "retour": page_precedente(requete)},
        status_code=statut,
    )


def verifier_secrets_api() -> None:
    """Secrets propres à l'API, facultatifs pour le job : leur absence arrête le serveur au
    démarrage plutôt qu'à la première requête."""
    r = reglages()
    manquants = [
        f"BITUMAP_{nom.upper()}" for nom in ("altcha_hmac", "sel_origine") if not getattr(r, nom)
    ]
    if manquants:
        raise RuntimeError(f"secrets de l'API absents : {', '.join(manquants)}")


@asynccontextmanager
async def _demarrage(app: FastAPI):
    verifier_secrets_api()
    yield


def creer_application() -> FastAPI:
    app = FastAPI(
        title="bitumap", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_demarrage
    )  # pas de documentation publique de l'API

    @app.middleware("http")
    async def en_tetes(requete: Request, suite):
        reponse = await suite(requete)
        for nom, valeur in EN_TETES_SECURITE.items():
            reponse.headers.setdefault(nom, valeur)
        return reponse

    @app.exception_handler(ErreurPublique)
    async def _erreur_publique(requete: Request, exc: ErreurPublique):
        return reponse_erreur(requete, exc.statut, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _erreur_http(requete: Request, exc: StarletteHTTPException):
        messages = {401: "Connexion requise.", 404: "Page introuvable.", 405: "Méthode refusée."}
        return reponse_erreur(
            requete, exc.status_code, "http", messages.get(exc.status_code, "Requête refusée.")
        )

    @app.exception_handler(RequestValidationError)
    async def _erreur_validation(requete: Request, exc: RequestValidationError):
        return reponse_erreur(requete, 400, "saisie_invalide", "Saisie invalide.")

    @app.exception_handler(Exception)
    async def _erreur_interne(requete: Request, exc: Exception):
        journal.exception("erreur interne")  # détail dans le journal uniquement (FR-025)
        return reponse_erreur(
            requete, 500, "erreur_interne", "Une erreur est survenue. Réessayez plus tard."
        )

    @app.get("/health")
    def sante() -> dict:
        return {"etat": "ok"}

    @app.get("/.well-known/security.txt")
    def security_txt() -> PlainTextResponse:
        # RFC 9116 ; « Expires » glissant (moins d'un an) : le fichier ne périme jamais.
        r = reglages()
        expire = (datetime.now(UTC) + timedelta(days=180)).strftime("%Y-%m-%dT00:00:00Z")
        return PlainTextResponse(
            f"Contact: {r.contact_securite}\n"
            f"Expires: {expire}\n"
            "Preferred-Languages: fr, en\n"
            f"Canonical: {r.url_publique.rstrip('/')}/.well-known/security.txt\n"
        )

    from bitumap.api import antibot, auth, compte, demandes, pages, parcours, terrain

    app.include_router(antibot.routeur)
    app.include_router(auth.routeur)
    app.include_router(compte.routeur)
    app.include_router(pages.routeur)
    app.include_router(demandes.routeur)
    app.include_router(terrain.routeur)
    app.include_router(parcours.routeur)
    app.mount("/statique", StaticFiles(directory=str(DOSSIER / "statique")), name="statique")
    return app
