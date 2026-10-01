"""Aides des tests de relevés terrain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from bitumap import stockage
from bitumap.config import reglages
from bitumap.terrain.photos import cle_quarantaine

JSON = {"accept": "application/json"}
# « Paix - Verdun », quai 23742 (Courbevoie) : position du rapport figé
POINT = "A23742"


def saisie(**champs) -> dict:
    corps = {
        "commune_insee": "92026",
        "point_id": POINT,
        "cree_le": datetime.now(UTC).isoformat(),
        "niveau": "marque",
    }
    corps.update(champs)
    return corps


def deposer(client, csrf, releve_id=None, **champs):
    releve_id = releve_id or str(uuid.uuid4())
    reponse = client.put(
        f"/terrain/releves/{releve_id}", json={**saisie(**champs), "csrf": csrf}, headers=JSON
    )
    return releve_id, reponse


def envoyer_photo(client, csrf, releve_id, contenu: bytes, type_="image/jpeg", photo_id=None):
    """Formulaire, dépôt simulé dans la quarantaine (le téléphone poste directement au
    stockage), puis confirmation. Renvoie (photo_id, réponse du formulaire, confirmation)."""
    photo_id = photo_id or str(uuid.uuid4())
    base = f"/terrain/releves/{releve_id}/photos/{photo_id}"
    formulaire = client.post(
        f"{base}/formulaire",
        json={"csrf": csrf, "octets": len(contenu), "type": type_},
        headers=JSON,
    )
    if formulaire.status_code != 200:
        return photo_id, formulaire, None
    stockage.ecrire(reglages().bucket_terrain, cle_quarantaine(photo_id), contenu, type_)
    confirmation = client.post(
        f"{base}/confirmation", json={"csrf": csrf, "lon": 2.2606, "lat": 48.9008}, headers=JSON
    )
    return photo_id, formulaire, confirmation
