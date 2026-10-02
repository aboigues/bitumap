"""Purge des données expirées (FR-026, FR-027), appelée au début de chaque lot."""

from __future__ import annotations

from bitumap.config import reglages
from bitumap.db import connexion


def purger() -> dict[str, int]:
    mois = reglages().compte_inactif_mois
    requetes = {
        "comptes_inactifs": (
            "DELETE FROM compte WHERE derniere_connexion < now() - make_interval(months => %s)",
            (mois,),
        ),
        "liens": ("DELETE FROM lien_connexion WHERE expire_le < now() - interval '1 day'", ()),
        "sessions": ("DELETE FROM session WHERE expire_le < now()", ()),
        "preuves": ("DELETE FROM preuve_antibot WHERE utilisee_le < now() - interval '1 hour'", ()),
        "compteurs": ("DELETE FROM compteur_quota WHERE expire_le < now()", ()),
        # Parcours de surveillance (006) : adresse de départ gardée 24 h au plus (SC-006).
        "parcours": ("DELETE FROM parcours WHERE expire_le < now()", ()),
    }
    resultat = {}
    with connexion() as conn:
        for nom, (sql, params) in requetes.items():
            resultat[nom] = conn.execute(sql, params).rowcount
    return resultat
