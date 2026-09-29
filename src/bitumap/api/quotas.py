"""Quotas (FR-005, FR-026 ; data-model.md ``compteur_quota``).

Chaque compteur est une ligne ``compteur_quota`` dont la clé contient la période (heure ou
jour) : l'incrément est atomique (``INSERT … ON CONFLICT DO UPDATE``) et la ligne expire à
la fin de sa période, au plus tard 24 h après (purge au début de chaque lot).

Les adresses IP et e-mails n'apparaissent jamais en clair dans les clés : on stocke une
empreinte HMAC avec un sel dérivé du secret ``bitumap-sel-origine`` et de la date du jour,
donc renouvelé chaque jour (deux jours différents donnent deux empreintes sans lien).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import Request

from bitumap.api.application import ErreurPublique
from bitumap.config import reglages
from bitumap.db import connexion

HEURE = timedelta(hours=1)
JOUR = timedelta(days=1)


def _sel_du_jour(maintenant: datetime) -> bytes:
    secret = reglages().sel_origine.get_secret_value().encode()
    return hmac.new(secret, f"{maintenant:%Y-%m-%d}".encode(), hashlib.sha256).digest()


def empreinte_salee(valeur: str, maintenant: datetime | None = None) -> str:
    maintenant = maintenant or datetime.now(UTC)
    return hmac.new(_sel_du_jour(maintenant), valeur.encode(), hashlib.sha256).hexdigest()[:32]


def adresse_origine(requete: Request) -> str:
    if reglages().origine_via_proxy:
        transmis = requete.headers.get("x-forwarded-for", "")
        if dernier := transmis.rsplit(",", 1)[-1].strip():
            return dernier
    return requete.client.host if requete.client else "inconnue"


def origine(requete: Request) -> str:
    return empreinte_salee(adresse_origine(requete))


def _periode(maintenant: datetime, duree: timedelta) -> tuple[str, datetime]:
    if duree == HEURE:
        debut = maintenant.replace(minute=0, second=0, microsecond=0)
        return f"{debut:%Y-%m-%dT%H}", debut + HEURE
    debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    return f"{debut:%Y-%m-%d}", debut + JOUR


def cle(prefixe: str, duree: timedelta, maintenant: datetime | None = None) -> tuple[str, datetime]:
    """Clé du compteur pour la période courante et sa date d'expiration."""
    periode, fin = _periode(maintenant or datetime.now(UTC), duree)
    return f"{prefixe}:{periode}", fin


def consommer(conn, prefixe: str, duree: timedelta, plafond: int) -> bool:
    """Incrémente le compteur si le plafond n'est pas atteint. Renvoie ``False`` sinon.

    Atomique : deux requêtes simultanées ne peuvent pas dépasser le plafond.
    """
    nom, fin = cle(prefixe, duree)
    ligne = conn.execute(
        "INSERT INTO compteur_quota (cle, valeur, expire_le) VALUES (%s, 1, %s)"
        " ON CONFLICT (cle) DO UPDATE SET valeur = compteur_quota.valeur + 1"
        " WHERE compteur_quota.valeur < %s"
        " RETURNING valeur",
        (nom, fin, plafond),
    ).fetchone()
    return ligne is not None and ligne["valeur"] <= plafond


def limiter(prefixe: str, duree: timedelta, plafond: int, code: str, message: str) -> None:
    with connexion() as conn:
        if not consommer(conn, prefixe, duree, plafond):
            raise ErreurPublique(429, code, message)


# Préfixes des clés (data-model.md)
def generation_compte(compte_id: str) -> str:
    return f"generation:compte:{compte_id}"


GENERATION_GLOBALE = "generation:global"


def lien_email(email: str) -> str:
    return f"lien:email:{empreinte_salee(email)}"


def lien_origine(requete: Request) -> str:
    return f"lien:origine:{origine(requete)}"


def defi_origine(requete: Request) -> str:
    return f"defi:origine:{origine(requete)}"
