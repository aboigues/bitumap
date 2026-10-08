"""Relevés terrain (003, contracts/http-api.md) : pages de saisie, relevés, photos.

Toutes les routes exigent une session ; toute écriture exige le jeton ``csrf``. Les routes à
chemin fixe (``releves``, ``photos``, ``manifeste``) sont déclarées avant ``/terrain/{insee}``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from bitumap.api.application import DOSSIER, ErreurPublique, gabarits
from bitumap.api.auth import MainteneurRequis, SessionRequise, est_mainteneur, verifier_csrf
from bitumap.api.demandes import page_choix_commune
from bitumap.config import reglages
from bitumap.score.methode import LIBELLES_GROUPES
from bitumap.terrain import depot, export, moderation, photos
from bitumap.terrain.points import points_en_vigueur

routeur = APIRouter(prefix="/terrain")
gabarits.env.globals["libelles_niveau"] = lambda groupe: LIBELLES_GROUPES.get(groupe, groupe)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_INSEE = re.compile(r"^\d{5}$")
_POINT = re.compile(r"^[A-Z][0-9]{1,20}$")


def _origines_stockage() -> str:
    """Origines autorisées pour l'envoi direct des photos (R4) : style chemin et style hôte."""
    r = reglages()
    base = urlsplit(r.s3_endpoint or "https://s3.fr-par.scw.cloud")
    return f"{base.scheme}://{base.netloc} {base.scheme}://{r.bucket_terrain}.{base.netloc}"


def en_tetes_terrain() -> dict[str, str]:
    """En-têtes propres aux pages de terrain (R4, R9) ; les autres pages gardent ceux de 002."""
    return {
        "Content-Security-Policy": (
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
            f"script-src 'self'; connect-src 'self' {_origines_stockage()}; "
            "worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        ),
        "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
        "Cache-Control": "private, no-store",
    }


def _uuid(valeur: str) -> str:
    if not _UUID.match(valeur):
        raise ErreurPublique(404, "http", "Page introuvable.")
    return valeur


async def _json(requete: Request) -> dict:
    try:
        corps = await requete.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as erreur:
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.") from erreur
    if not isinstance(corps, dict):
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.")
    return corps


def _reponse(statut: int, corps: dict) -> JSONResponse:
    return JSONResponse(corps, status_code=statut, headers={"Cache-Control": "no-store"})


# --- Chemins fixes ----------------------------------------------------------------------


@routeur.get("/manifeste.webmanifest")
def manifeste() -> Response:
    contenu = (DOSSIER / "statique" / "terrain" / "manifeste.webmanifest").read_bytes()
    return Response(contenu, media_type="application/manifest+json")


@routeur.put("/releves/{releve_id}")
async def deposer(requete: Request, releve_id: str, session: SessionRequise) -> JSONResponse:
    _uuid(releve_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.pop("csrf", "")))
    if not corps.get("niveau"):
        raise ErreurPublique(400, "niveau_requis", "Le niveau d'orniérage est obligatoire.")
    try:
        saisie = depot.SaisieReleve.model_validate(corps)
    except ValidationError as erreur:
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.") from erreur
    resultat = depot.creer(session.compte_id, releve_id, saisie)
    return _reponse(resultat.statut, resultat.corps)


@routeur.get("/releves/{releve_id}")
def lire_releve(releve_id: str, session: SessionRequise) -> JSONResponse:
    vue = depot.releve(_uuid(releve_id), session.compte_id)
    if vue is None:
        raise ErreurPublique(404, "releve_inconnu", "Relevé introuvable.")
    return _reponse(200, vue)


@routeur.post("/releves/{releve_id}/versions")
async def corriger(requete: Request, releve_id: str, session: SessionRequise) -> JSONResponse:
    _uuid(releve_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.pop("csrf", "")))
    if not corps.get("niveau"):
        raise ErreurPublique(400, "niveau_requis", "Le niveau d'orniérage est obligatoire.")
    try:
        correction = depot.Correction.model_validate(corps)
    except ValidationError as erreur:
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.") from erreur
    resultat = depot.corriger(session.compte_id, releve_id, correction)
    return _reponse(resultat.statut, resultat.corps)


@routeur.post("/releves/{releve_id}/retrait")
async def retirer_releve(requete: Request, releve_id: str, session: SessionRequise) -> JSONResponse:
    _uuid(releve_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.get("csrf", "")))
    moderation_rgpd = corps.get("rgpd") is True and est_mainteneur(session)
    depot.retirer(releve_id, session.compte_id, _texte(corps.get("motif")), moderation_rgpd)
    return _reponse(200, {"id": releve_id, "retire": True})


@routeur.post("/photos/{photo_id}/retrait")
async def retirer_photo(requete: Request, photo_id: str, session: SessionRequise) -> JSONResponse:
    _uuid(photo_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.get("csrf", "")))
    motif = _texte(corps.get("motif"))
    # RGPD (toutes les versions du fichier supprimées) : mainteneur seul, sur demande
    # explicite ; sinon retrait simple par l'auteur, fichier conservé (R12).
    if corps.get("rgpd") is True and est_mainteneur(session):
        photos.retirer_rgpd(photo_id, session.compte_id, motif)
    else:
        photos.retirer_par_auteur(photo_id, session.compte_id, motif)
    return _reponse(200, {"id": photo_id, "retire": True})


def _texte(valeur) -> str | None:
    return valeur if isinstance(valeur, str) else None


@routeur.post("/releves/{releve_id}/photos/{photo_id}/formulaire")
async def formulaire_photo(
    requete: Request, releve_id: str, photo_id: str, session: SessionRequise
) -> JSONResponse:
    _uuid(releve_id), _uuid(photo_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.get("csrf", "")))
    try:
        octets = int(corps.get("octets", 0))
    except (TypeError, ValueError) as erreur:
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.") from erreur
    envoi = photos.formulaire(
        session.compte_id, releve_id, photo_id, octets, str(corps.get("type", ""))
    )
    return _reponse(200, envoi)


@routeur.post("/releves/{releve_id}/photos/{photo_id}/confirmation")
async def confirmer_photo(
    requete: Request, releve_id: str, photo_id: str, session: SessionRequise
) -> JSONResponse:
    _uuid(releve_id), _uuid(photo_id)
    corps = await _json(requete)
    verifier_csrf(session, str(corps.get("csrf", "")))
    try:
        lon = float(corps["lon"]) if corps.get("lon") is not None else None
        lat = float(corps["lat"]) if corps.get("lat") is not None else None
        prise_le = datetime.fromisoformat(corps["prise_le"]) if corps.get("prise_le") else None
    except (TypeError, ValueError) as erreur:
        raise ErreurPublique(400, "saisie_invalide", "Saisie invalide.") from erreur
    resultat = photos.confirmer(session.compte_id, releve_id, photo_id, lon, lat, prise_le)
    return _reponse(201, resultat)


@routeur.get("")
def choix_commune(
    requete: Request, session: SessionRequise, q: str = "", insee: str = ""
) -> Response:
    """Entrée « Relevés terrain » du menu : choix d'une commune à rapport disponible (008)."""
    reponse = page_choix_commune(requete, session, "terrain", q, insee)
    reponse.headers.update(en_tetes_terrain())
    return reponse


@routeur.get("/moderation")
def page_moderation(requete: Request, session: MainteneurRequis, q: str = "") -> Response:
    resultats = moderation.rechercher(q[:100]) if q.strip() else None
    reponse = gabarits.TemplateResponse(
        requete,
        "terrain/moderation.html",
        {
            "session": session,
            "q": q[:100],
            "resultats": resultats,
            "critere_invalide": bool(q.strip()) and resultats is None,
            "niveaux": depot.LIBELLES_NIVEAUX,
        },
    )
    reponse.headers.update(en_tetes_terrain())
    return reponse


@routeur.get("/photos/{photo_id}")
def servir_photo(photo_id: str, session: SessionRequise) -> Response:
    contenu = photos.lire(_uuid(photo_id), session.compte_id, est_mainteneur(session))
    if contenu is None:  # aussi pour un autre compte : aucune fuite d'existence (R5)
        raise ErreurPublique(404, "http", "Page introuvable.")
    return Response(
        contenu, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
    )


# --- Pages par commune ------------------------------------------------------------------


def _commune(insee: str):
    if not _INSEE.match(insee):
        raise ErreurPublique(404, "http", "Page introuvable.")
    empreinte, points = points_en_vigueur(insee)
    if empreinte is None:
        raise ErreurPublique(
            404, "rapport_absent", "Aucun rapport en vigueur pour cette commune : demandez-le."
        )
    return empreinte, points


@routeur.get("/{insee}")
def page_points(requete: Request, insee: str, session: SessionRequise) -> Response:
    empreinte, points = _commune(insee)
    releves = depot.derniers_releves(insee, session.compte_id)
    absents = [r for pid, r in releves.items() if pid not in points]
    reponse = gabarits.TemplateResponse(
        requete,
        "terrain/points.html",
        {
            "session": session,
            "insee": insee,
            "empreinte": empreinte,
            "points": sorted(points.values(), key=lambda p: p.rang),
            "releves": releves,
            "absents": absents,
            "niveaux": depot.LIBELLES_NIVEAUX,
            "sources": depot.LIBELLES_SOURCES,
        },
    )
    reponse.headers.update(en_tetes_terrain())
    return reponse


def _telechargement(contenu: bytes, type_media: str, nom: str) -> Response:
    return Response(
        contenu,
        media_type=type_media,
        headers={
            "Content-Disposition": f'attachment; filename="{nom}"',
            "Cache-Control": "private, no-store",
        },
    )


@routeur.get("/{insee}/releves.csv")
def export_csv(insee: str, session: SessionRequise) -> Response:
    _, points = _commune(insee)
    donnees = export.lignes(insee, session.compte_id, points)
    return _telechargement(
        export.en_csv(donnees), "text/csv; charset=utf-8", f"releves-{insee}.csv"
    )


@routeur.get("/{insee}/releves.geojson")
def export_geojson(insee: str, session: SessionRequise) -> Response:
    _, points = _commune(insee)
    donnees = export.en_geojson(export.lignes(insee, session.compte_id, points))
    return _telechargement(
        json.dumps(donnees, ensure_ascii=False).encode(),
        "application/geo+json",
        f"releves-{insee}.geojson",
    )


@routeur.get("/{insee}/echantillon_refection.json")
def export_echantillon(insee: str, session: SessionRequise) -> Response:
    _, points = _commune(insee)
    donnees = export.echantillon_refection(insee, points)
    return _telechargement(
        json.dumps(donnees, ensure_ascii=False, indent=1).encode(),
        "application/json",
        f"echantillon_refection-{insee}.json",
    )


@routeur.get("/{insee}/{point_id}")
def page_saisie(requete: Request, insee: str, point_id: str, session: SessionRequise) -> Response:
    if not _POINT.match(point_id):
        raise ErreurPublique(404, "http", "Page introuvable.")
    empreinte, points = _commune(insee)
    historique = depot.historique(insee, point_id, session.compte_id)
    point = points.get(point_id)
    if point is None and not historique:
        raise ErreurPublique(404, "point_inconnu", "Ce point n'existe pas dans le rapport.")
    reponse = gabarits.TemplateResponse(
        requete,
        "terrain/saisie.html",
        {
            "session": session,
            "insee": insee,
            "empreinte": empreinte,
            "point": point,
            "point_id": point_id,
            "historique": historique,
            "niveaux": depot.LIBELLES_NIVEAUX,
            "sources": depot.LIBELLES_SOURCES,
            "annee": datetime.now().year,
        },
    )
    reponse.headers.update(en_tetes_terrain())
    return reponse
