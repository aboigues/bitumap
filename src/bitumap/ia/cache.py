"""Cache des réponses IA par point (research R7-bis) : clé = point, millésimes d'orthophoto,
modèle, version du prompt. Un succès du cache ne coûte rien et garantit la reproductibilité."""

from __future__ import annotations

import json

from bitumap.db import connexion


def lire(point_id: str, millesimes: list[int], modele: str, version_prompt: str) -> dict | None:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT reponse FROM ia_cache_point WHERE point_id = %s AND millesimes = %s"
            " AND modele = %s AND version_prompt = %s",
            (point_id, ",".join(map(str, millesimes)), modele, version_prompt),
        ).fetchone()
    return None if ligne is None else ligne["reponse"]


def ecrire(
    point_id: str, millesimes: list[int], modele: str, version_prompt: str, reponse: dict
) -> None:
    with connexion() as conn:
        conn.execute(
            "INSERT INTO ia_cache_point (point_id, millesimes, modele, version_prompt, reponse)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (point_id, ",".join(map(str, millesimes)), modele, version_prompt, json.dumps(reponse)),
        )
