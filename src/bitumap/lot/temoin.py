"""Témoins de la file dans le stockage objet (T096) : le job ne réveille la base que s'il a
du travail.

La base Serverless SQL reste active quelques minutes après chaque connexion et se facture à
l'usage : un job qui l'interroge toutes les 15 minutes coûterait 16 à 33 € par mois à vide
(`infra/tofu/README.md`). L'API dépose donc un objet vide ``file/<demande_id>`` dans le
bucket du cache à chaque mise en file ; le job liste ces objets, sans connexion à la base.
Un témoin par demande : le job ne retire que ceux qu'il a listés avant le lot et dont la
demande n'est plus active, sans course avec une mise en file pendant le lot.

``schema/<numéro>`` note la dernière migration appliquée par le job : une nouvelle image
qui apporte une migration ouvre la base à son premier passage (T097).
"""

from __future__ import annotations

from datetime import datetime

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.db.migrer import migrations

PREFIXE_FILE = "file/"
PREFIXE_SCHEMA = "schema/"


def _bucket() -> str:
    return reglages().bucket_cache


def signaler(demande_id: str) -> None:
    """Appelé par l'API à chaque mise en file ou rattachement (idempotent)."""
    stockage.ecrire(_bucket(), f"{PREFIXE_FILE}{demande_id}", b"", "text/plain")


def en_attente() -> list[str]:
    """Identifiants des demandes signalées (aucune connexion à la base)."""
    return [cle.removeprefix(PREFIXE_FILE) for cle in stockage.lister(_bucket(), PREFIXE_FILE)]


def nettoyer(demandes: list[str]) -> int:
    """Retire les témoins des demandes qui ne sont plus en file ni en cours (terminées, en
    échec ou inconnues) ; renvoie leur nombre. Les autres restent pour le lot suivant."""
    if not demandes:
        return 0
    with connexion() as conn:
        actives = {
            str(ligne["id"])
            for ligne in conn.execute(
                "SELECT id FROM demande WHERE id::text = ANY(%s)"
                " AND etat IN ('en_file', 'en_cours')",
                (demandes,),
            )
        }
    retires = [d for d in demandes if d not in actives]
    for demande in retires:
        stockage.supprimer(_bucket(), f"{PREFIXE_FILE}{demande}")
    return len(retires)


def _derniere_migration() -> int:
    return migrations()[-1][0]


def schema_note() -> bool:
    """Vrai si la dernière migration de cette image a déjà été appliquée et notée."""
    return stockage.existe(_bucket(), f"{PREFIXE_SCHEMA}{_derniere_migration()}")


def noter_schema() -> None:
    stockage.ecrire(_bucket(), f"{PREFIXE_SCHEMA}{_derniere_migration()}", b"", "text/plain")


def passage_quotidien(maintenant: datetime) -> bool:
    """Premier créneau de l'heure UTC de purge : la base est ouverte une fois par jour, même
    sans demande (purge des données expirées, lots interrompus)."""
    r = reglages()
    return maintenant.hour == r.lot_heure_quotidienne_utc and (
        maintenant.minute < r.lot_intervalle_min
    )
