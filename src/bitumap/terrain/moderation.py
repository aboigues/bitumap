"""Recherche de modération (003 US5 : FR-016, R12) : réservée au mainteneur.

Le mainteneur voit tous les relevés, y compris retirés (trace), l'adresse complète de
l'auteur (R6) et toutes les photos avec leur état. Critère : identifiant de relevé ou de
photo, code INSEE de commune, ou identifiant de point.
"""

from __future__ import annotations

import re

from bitumap.db import connexion
from bitumap.terrain.pseudonyme import pseudonyme

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_INSEE = re.compile(r"^\d{5}$")
_POINT = re.compile(r"^[A-Z][0-9]{1,20}$")
LIMITE = 200


def _critere(q: str) -> tuple[str, tuple] | None:
    """Filtre SQL constant et paramètres ; ``None`` si la saisie n'est pas un critère."""
    q = q.strip()
    if _UUID.match(q.lower()):
        q = q.lower()
        return (
            "r.id = %s OR r.id IN (SELECT releve_id FROM photo WHERE id = %s)",
            (q, q),
        )
    if _INSEE.match(q):
        return "r.commune_insee = %s", (q,)
    if _POINT.match(q.upper()):
        return "r.point_id = %s", (q.upper(),)
    return None


def rechercher(q: str) -> list[dict] | None:
    """Relevés correspondants (du plus récent au plus ancien), ``None`` si critère invalide."""
    critere = _critere(q)
    if critere is None:
        return None
    filtre, parametres = critere
    with connexion() as conn:
        releves = conn.execute(
            "SELECT r.*, c.email, v.version, v.niveau, v.observation FROM releve r"  # noqa: S608
            " JOIN LATERAL (SELECT * FROM releve_version WHERE releve_id = r.id"
            " ORDER BY version DESC LIMIT 1) v ON true"
            " LEFT JOIN compte c ON c.id = r.compte_id"
            f" WHERE {filtre} ORDER BY r.cree_le DESC LIMIT {LIMITE}",
            parametres,
        ).fetchall()
        ids = [r["id"] for r in releves]
        photos = (
            conn.execute(
                "SELECT id, releve_id, etat, motif_retrait, retire_le FROM photo"
                " WHERE releve_id = ANY(%s) ORDER BY cree_le",
                (ids,),
            ).fetchall()
            if ids
            else []
        )
    resultat = []
    for r in releves:
        compte = str(r["compte_id"]) if r["compte_id"] else None
        resultat.append(
            {
                "id": str(r["id"]),
                "commune_insee": r["commune_insee"],
                "point_id": r["point_id"],
                "point_designation": r["point_designation"],
                "cree_le": r["cree_le"].isoformat(),
                "version": r["version"],
                "niveau": r["niveau"],
                "observation": r["observation"],
                "email": r["email"],
                "auteur": pseudonyme(compte, r["email"]),
                "retire_le": r["retire_le"].isoformat() if r["retire_le"] else None,
                "motif_retrait": r["motif_retrait"],
                "photos": [
                    {
                        "id": str(p["id"]),
                        "etat": p["etat"],
                        "motif_retrait": p["motif_retrait"],
                    }
                    for p in photos
                    if p["releve_id"] == r["id"]
                ],
            }
        )
    return resultat
