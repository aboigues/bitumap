"""E-mails du service (FR-028) : contenu minimal, envoi hébergé dans l'UE.

Mode « console » en local (rien n'est envoyé : le message est journalisé), « tem » en
production (Scaleway Transactional Email, API REST).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from bitumap.config import reglages

journal = logging.getLogger("bitumap.courriel")

# Messages envoyés en mode console, pour les tests.
ENVOYES: list[Courriel] = []


@dataclass(frozen=True)
class Courriel:
    destinataire: str
    sujet: str
    texte: str


def lien_connexion(destinataire: str, lien: str, validite_min: int) -> Courriel:
    return Courriel(
        destinataire,
        "Votre lien de connexion à bitumap",
        f"Pour vous connecter à bitumap, ouvrez ce lien (valable {validite_min} minutes, "
        f"utilisable une seule fois) :\n\n{lien}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
    )


def rapport_pret(destinataire: str, commune: str, lien: str) -> Courriel:
    return Courriel(
        destinataire,
        f"Rapport prêt : {commune}",
        f"Le rapport de risque d'orniérage de {commune} est prêt.\n\n{lien}\n\n"
        "La consultation nécessite d'être connecté.",
    )


def rapport_en_echec(destinataire: str, commune: str) -> Courriel:
    return Courriel(
        destinataire,
        f"Rapport non généré : {commune}",
        f"La génération du rapport de {commune} n'a pas abouti. "
        "Vous pouvez renouveler la demande plus tard.",
    )


def alerte_mainteneur(sujet: str, texte: str) -> Courriel | None:
    destinataire = reglages().email_mainteneur
    if not destinataire:
        journal.warning("alerte non envoyée (aucun destinataire configuré) : %s", sujet)
        return None
    return Courriel(destinataire, f"[bitumap] {sujet}", texte)


def envoyer(courriel: Courriel | None) -> None:
    if courriel is None:
        return
    r = reglages()
    if r.courriel_mode == "console":
        ENVOYES.append(courriel)
        journal.info("courriel (console) à %s : %s\n%s", "***", courriel.sujet, courriel.texte)
        return
    if r.courriel_mode != "tem" or r.tem_cle is None:
        raise RuntimeError("envoi d'e-mails non configuré")
    reponse = httpx.post(
        f"https://api.scaleway.com/transactional-email/v1alpha1/regions/{r.s3_region}/emails",
        headers={"X-Auth-Token": r.tem_cle.get_secret_value()},
        json={
            "from": {"email": r.email_expediteur, "name": "bitumap"},
            "to": [{"email": courriel.destinataire}],
            "subject": courriel.sujet,
            "text": courriel.texte,
            "project_id": r.projet_scaleway,
        },
        timeout=15,
    )
    reponse.raise_for_status()
