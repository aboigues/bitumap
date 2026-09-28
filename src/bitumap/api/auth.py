"""Connexion sans mot de passe par lien e-mail (FR-006, FR-006b ; research R4).

- lien : jeton aléatoire de 32 octets, seule son empreinte SHA-256 est stockée ; usage
  unique ; valable ``lien_validite_min`` minutes ;
- session : identifiant aléatoire dans un cookie ``__Host-session`` (Secure, HttpOnly,
  SameSite=Lax), empreinte en base, ``session_jours`` jours ;
- jeton anti-CSRF lié à la session, vérifié sur chaque POST authentifié.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from bitumap import courriel
from bitumap.api.application import ErreurPublique, gabarits
from bitumap.config import reglages
from bitumap.db import connexion

routeur = APIRouter()

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,63}$")


@dataclass(frozen=True)
class Session:
    compte_id: str
    email: str
    csrf: str


def empreinte(valeur: str) -> bytes:
    return hashlib.sha256(valeur.encode()).digest()


def nom_cookie() -> str:
    return "__Host-session" if reglages().cookies_securises else "session"


def normaliser_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 320 or not _EMAIL.match(email):
        raise ErreurPublique(400, "email_invalide", "Adresse e-mail invalide.")
    return email


def emettre_lien(email: str) -> str | None:
    """Crée un lien de connexion et l'envoie. Renvoie le jeton (utile aux tests)."""
    r = reglages()
    jeton = secrets.token_urlsafe(32)
    maintenant = datetime.now(UTC)
    with connexion() as conn:
        conn.execute(
            "INSERT INTO lien_connexion (empreinte_jeton, email, emis_le, expire_le)"
            " VALUES (%s, %s, %s, %s)",
            (
                empreinte(jeton),
                email,
                maintenant,
                maintenant + timedelta(minutes=r.lien_validite_min),
            ),
        )
    lien = f"{r.url_publique.rstrip('/')}/connexion/{jeton}"
    courriel.envoyer(courriel.lien_connexion(email, lien, r.lien_validite_min))
    return jeton


def ouvrir_session(jeton: str) -> tuple[str, str] | None:
    """Consomme le lien (usage unique) et ouvre une session. Renvoie (id_session, csrf)."""
    r = reglages()
    with connexion() as conn:
        lien = conn.execute(
            "UPDATE lien_connexion SET utilise_le = now()"
            " WHERE empreinte_jeton = %s AND utilise_le IS NULL AND expire_le > now()"
            " RETURNING email",
            (empreinte(jeton),),
        ).fetchone()
        if lien is None:
            return None
        compte = conn.execute(
            "INSERT INTO compte (email) VALUES (%s)"
            " ON CONFLICT (email) DO UPDATE SET derniere_connexion = now()"
            " RETURNING id",
            (lien["email"],),
        ).fetchone()
        conn.execute(
            "UPDATE lien_connexion SET compte_id = %s WHERE empreinte_jeton = %s",
            (compte["id"], empreinte(jeton)),
        )
        id_session = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        conn.execute(
            "INSERT INTO session (empreinte_id, compte_id, jeton_csrf, expire_le)"
            " VALUES (%s, %s, %s, now() + make_interval(days => %s))",
            (empreinte(id_session), compte["id"], csrf, r.session_jours),
        )
    return id_session, csrf


def session_courante(requete: Request) -> Session | None:
    valeur = requete.cookies.get(nom_cookie())
    if not valeur:
        return None
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT s.compte_id, c.email, s.jeton_csrf FROM session s"
            " JOIN compte c ON c.id = s.compte_id"
            " WHERE s.empreinte_id = %s AND s.expire_le > now()",
            (empreinte(valeur),),
        ).fetchone()
    if ligne is None:
        return None
    return Session(str(ligne["compte_id"]), ligne["email"], ligne["jeton_csrf"])


def session_requise(requete: Request) -> Session:
    session = session_courante(requete)
    if session is None:
        raise ErreurPublique(401, "connexion_requise", "Connexion requise.")
    return session


SessionRequise = Annotated[Session, Depends(session_requise)]


def verifier_csrf(session: Session, csrf: str) -> None:
    if not csrf or not hmac.compare_digest(session.csrf, csrf):
        raise ErreurPublique(403, "csrf_invalide", "Formulaire expiré : rechargez la page.")


@routeur.post("/connexion")
def demander_lien(requete: Request, email: Annotated[str, Form()] = "") -> Response:
    adresse = normaliser_email(email)
    # Contrôles antibot et quotas branchés ici en US2 (T060).
    emettre_lien(adresse)
    # Réponse identique que le compte existe ou non (FR-006b).
    return gabarits.TemplateResponse(requete, "lien_envoye.html", {})


@routeur.get("/connexion/{jeton}")
def valider_lien(jeton: str) -> Response:
    resultat = ouvrir_session(jeton)
    if resultat is None:
        raise ErreurPublique(
            410,
            "lien_expire_ou_utilise",
            "Ce lien a expiré ou a déjà été utilisé. Demandez-en un nouveau.",
        )
    id_session, _ = resultat
    reponse = RedirectResponse("/", status_code=303)
    reponse.set_cookie(
        nom_cookie(),
        id_session,
        max_age=reglages().session_jours * 86400,
        path="/",
        secure=reglages().cookies_securises,
        httponly=True,
        samesite="lax",
    )
    return reponse


@routeur.post("/deconnexion")
def deconnexion(
    requete: Request, session: SessionRequise, csrf: Annotated[str, Form()] = ""
) -> Response:
    verifier_csrf(session, csrf)
    valeur = requete.cookies.get(nom_cookie(), "")
    with connexion() as conn:
        conn.execute("DELETE FROM session WHERE empreinte_id = %s", (empreinte(valeur),))
    reponse = RedirectResponse("/", status_code=303)
    reponse.delete_cookie(nom_cookie(), path="/", secure=reglages().cookies_securises)
    return reponse
