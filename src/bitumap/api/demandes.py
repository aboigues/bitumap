"""Communes, demandes de rapport, suivi et consultation (contracts/http-api.md ; US1).

Antibot et quotas sont branchés en US2 (T060) : voir ``controles_avant_demande``.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from bitumap import stockage
from bitumap.api.application import ErreurPublique, gabarits
from bitumap.api.auth import SessionRequise, verifier_csrf
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.lot import versions
from bitumap.rapport.rendu import CSP_RAPPORT
from bitumap.territoire import ErreurTerritoire, commune_par_insee, communes_du_code_postal

routeur = APIRouter()
_EMPREINTE = re.compile(r"^[0-9a-f]{16}$")
_INSEE = re.compile(r"^\d{5}$")
DUREE_LOT_DEFAUT_MIN = 15


def _erreur_territoire(e: ErreurTerritoire) -> ErreurPublique:
    statut = 404 if e.code == "code_inexistant" else 400
    return ErreurPublique(statut, e.code, e.message)


def rapport_valide(insee: str) -> str | None:
    """Empreinte d'un rapport réutilisable (FR-008) : même empreinte courante et moins de
    ``cache_rapport_jours`` jours ; sinon ``None``."""
    empreinte = versions.empreinte_courante(insee)
    produit_le = stockage.date_rapport(insee, empreinte)
    if produit_le is None:
        return None
    limite = datetime.now(UTC) - timedelta(days=reglages().cache_rapport_jours)
    return empreinte if produit_le >= limite else None


def controles_avant_demande(requete: Request, session, altcha: str) -> None:
    """Point d'extension : antibot, quotas, budget (US2, T060)."""


@routeur.get("/communes")
def communes(requete: Request, session: SessionRequise, code_postal: str = "") -> Response:
    try:
        liste = communes_du_code_postal(code_postal)
    except ErreurTerritoire as e:
        raise _erreur_territoire(e) from e
    return gabarits.TemplateResponse(
        requete,
        "communes.html",
        {"session": session, "communes": liste, "code_postal": code_postal},
    )


@routeur.post("/demandes")
def demander(
    requete: Request,
    session: SessionRequise,
    insee: Annotated[str, Form()] = "",
    csrf: Annotated[str, Form()] = "",
    altcha: Annotated[str, Form()] = "",
) -> Response:
    verifier_csrf(session, csrf)
    if not _INSEE.match(insee):
        raise ErreurPublique(400, "commune_invalide", "Commune inconnue.")
    try:
        commune = commune_par_insee(insee)
    except ErreurTerritoire as e:
        raise _erreur_territoire(e) from e
    controles_avant_demande(requete, session, altcha)

    empreinte = rapport_valide(commune.insee)
    if empreinte:
        return RedirectResponse(f"/rapports/{commune.insee}/{empreinte}", status_code=303)

    empreinte = versions.empreinte_courante(commune.insee)
    with connexion() as conn:
        cree = conn.execute(
            "INSERT INTO demande (commune_insee, commune_nom, empreinte) VALUES (%s, %s, %s)"
            " ON CONFLICT (empreinte) WHERE etat IN ('en_file', 'en_cours') DO NOTHING"
            " RETURNING id",
            (commune.insee, commune.nom, empreinte),
        ).fetchone()
        if cree is None:  # demande active existante : rattachement sans décompte (US2-6)
            existante = conn.execute(
                "SELECT id FROM demande WHERE empreinte = %s AND etat IN ('en_file', 'en_cours')",
                (empreinte,),
            ).fetchone()
            demande_id, compte_quota = existante["id"], False
        else:
            demande_id, compte_quota = cree["id"], True
        conn.execute(
            "INSERT INTO demandeur_demande (demande_id, compte_id, compte_quota)"
            " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (demande_id, session.compte_id, compte_quota),
        )
    return RedirectResponse(f"/demandes/{demande_id}", status_code=303)


def _prochain_declenchement(maintenant: datetime) -> datetime:
    pas = reglages().lot_intervalle_min
    minutes = (maintenant.minute // pas + 1) * pas
    base = maintenant.replace(minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minutes)


def _duree_moyenne_lot_min() -> float:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT avg(extract(epoch FROM termine_le - demarre_le)) / 60 AS m FROM"
            " (SELECT * FROM lot WHERE termine_le IS NOT NULL AND nb_demandes > 0"
            "  ORDER BY demarre_le DESC LIMIT 10) l"
        ).fetchone()
    return float(ligne["m"]) if ligne and ligne["m"] else DUREE_LOT_DEFAUT_MIN


def suivi_de(demande_id: str, compte_id: str) -> dict | None:
    with connexion() as conn:
        d = conn.execute(
            "SELECT d.* FROM demande d JOIN demandeur_demande dd ON dd.demande_id = d.id"
            " WHERE d.id = %s AND dd.compte_id = %s",
            (demande_id, compte_id),
        ).fetchone()
        if d is None:
            return None
        position = None
        if d["etat"] == "en_file":
            position = conn.execute(
                "SELECT count(*) + 1 AS p FROM demande WHERE etat = 'en_file' AND cree_le < %s",
                (d["cree_le"],),
            ).fetchone()["p"]
    suivi = dict(d)
    suivi["position"] = position
    if position is not None:
        lots_avant = math.ceil(position / reglages().lot_taille) - 1
        debut = _prochain_declenchement(datetime.now(UTC))
        suivi["heure_estimee"] = debut + timedelta(
            minutes=lots_avant * reglages().lot_intervalle_min + _duree_moyenne_lot_min()
        )
    return suivi


@routeur.get("/demandes/{demande_id}")
def suivi(requete: Request, demande_id: str, session: SessionRequise) -> Response:
    try:
        donnees = suivi_de(demande_id, session.compte_id)
    except Exception as e:  # identifiant mal formé
        raise ErreurPublique(404, "demande_inconnue", "Demande introuvable.") from e
    if donnees is None:
        raise ErreurPublique(404, "demande_inconnue", "Demande introuvable.")
    return gabarits.TemplateResponse(
        requete, "suivi.html", {"session": session, "demande": donnees}
    )


@routeur.get("/demandes")
def mes_demandes(requete: Request, session: SessionRequise) -> Response:
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT d.id, d.commune_nom, d.commune_insee, d.empreinte, d.etat, d.cree_le"
            " FROM demande d JOIN demandeur_demande dd ON dd.demande_id = d.id"
            " WHERE dd.compte_id = %s ORDER BY d.cree_le DESC LIMIT 100",
            (session.compte_id,),
        ).fetchall()
    return gabarits.TemplateResponse(
        requete, "demandes.html", {"session": session, "demandes": lignes}
    )


def _fichier_rapport(insee: str, empreinte: str, nom: str) -> bytes:
    if not _INSEE.match(insee) or not _EMPREINTE.match(empreinte):
        raise ErreurPublique(404, "rapport_inconnu", "Rapport introuvable.")
    contenu = stockage.lire(
        reglages().bucket_rapports, stockage.prefixe_rapport(insee, empreinte) + nom
    )
    if contenu is None:
        raise ErreurPublique(404, "rapport_inconnu", "Rapport introuvable.")
    return contenu


@routeur.get("/rapports/{insee}/{empreinte}")
def rapport(insee: str, empreinte: str, session: SessionRequise) -> Response:
    contenu = _fichier_rapport(insee, empreinte, "rapport.html")
    return Response(
        contenu,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": CSP_RAPPORT,
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )


@routeur.get("/rapports/{insee}/{empreinte}/points.geojson")
def points_geojson(insee: str, empreinte: str, session: SessionRequise) -> Response:
    return Response(
        _fichier_rapport(insee, empreinte, "points.geojson"),
        media_type="application/geo+json",
        headers={"Cache-Control": "private, no-store"},
    )
