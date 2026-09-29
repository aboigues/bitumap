"""Antibot ALTCHA auto-hébergé (FR-005, research R5).

- ``GET /altcha/defi`` : défi de preuve de travail signé par HMAC (secret
  ``bitumap-altcha-hmac``), valable ``altcha_validite_min`` minutes, 60 par heure et par
  origine ;
- ``verifier`` : contrôle la solution avec la bibliothèque ``altcha``, puis enregistre la
  signature du défi dans ``preuve_antibot`` : une preuve ne sert qu'une fois (purgée après
  1 h, bien après l'expiration du défi).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import altcha
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bitumap.api import quotas
from bitumap.api.application import ErreurPublique
from bitumap.config import reglages
from bitumap.db import connexion

routeur = APIRouter()

TAILLE_MAX = 4096  # une charge utile ALTCHA v2 fait environ 600 caractères


def _secret() -> str:
    return reglages().altcha_hmac.get_secret_value()


def creer_defi() -> dict:
    r = reglages()
    defi = altcha.create_challenge(
        r.altcha_algorithme,
        r.altcha_cout,
        expires_at=datetime.now(UTC) + timedelta(minutes=r.altcha_validite_min),
        hmac_secret=_secret(),
    )
    return defi.to_dict()


def _invalide() -> ErreurPublique:
    return ErreurPublique(
        400, "antibot_invalide", "Vérification anti-robot manquante ou expirée : réessayez."
    )


def verifier(charge: str) -> None:
    """Refuse une preuve absente, invalide, expirée ou déjà utilisée."""
    if not charge or len(charge) > TAILLE_MAX:
        raise _invalide()
    try:
        resultat = altcha.verify_solution(charge, _secret())
        signature = altcha.Payload.from_base64(charge).challenge.signature
    except Exception as e:  # charge mal formée : jamais de détail technique (FR-025)
        raise _invalide() from e
    if not resultat.verified or not signature:
        raise _invalide()
    with connexion() as conn:
        neuve = conn.execute(
            "INSERT INTO preuve_antibot (signature) VALUES (%s)"
            " ON CONFLICT (signature) DO NOTHING RETURNING signature",
            (signature,),
        ).fetchone()
    if neuve is None:
        raise _invalide()


@routeur.get("/altcha/defi")
def defi(requete: Request) -> JSONResponse:
    quotas.limiter(
        quotas.defi_origine(requete),
        quotas.HEURE,
        reglages().quota_defi_origine_heure,
        "trop_de_demandes",
        "Trop de tentatives : réessayez dans une heure.",
    )
    return JSONResponse(creer_defi(), headers={"Cache-Control": "no-store"})
