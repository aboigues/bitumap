"""Affichage de l'auteur d'un relevé (003 R6, FR-010) : pseudonyme stable et domaine.

« agent 7F3A · ville-courbevoie.fr » : l'adresse complète n'est jamais affichée aux autres
utilisateurs (seul le mainteneur la voit). Le pseudonyme est une empreinte à clé de
l'identifiant du compte, stable dans le temps (clé dérivée du secret ``sel_origine`` avec une
étiquette fixe, indépendante du sel quotidien des quotas).
"""

from __future__ import annotations

import hashlib
import hmac

from bitumap.config import reglages

AUTEUR_SUPPRIME = "auteur supprimé"
VOUS = "vous"


def _cle() -> bytes:
    secret = reglages().sel_origine.get_secret_value().encode()
    return hmac.new(secret, b"bitumap/terrain/pseudonyme", hashlib.sha256).digest()


def pseudonyme(compte_id: str | None, email: str | None, lecteur_id: str | None = None) -> str:
    if compte_id is None or not email:
        return AUTEUR_SUPPRIME
    if lecteur_id is not None and str(lecteur_id) == str(compte_id):
        return VOUS
    code = hmac.new(_cle(), str(compte_id).encode(), hashlib.sha256).hexdigest()[:4].upper()
    domaine = email.rsplit("@", 1)[-1]
    return f"agent {code} · {domaine}"
