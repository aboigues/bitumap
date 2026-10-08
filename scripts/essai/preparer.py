#!/usr/bin/env python3
"""Prépare l'essai local des interfaces par le mainteneur avant fusion (LL-031).

Base et stockage simulé de ``docker compose`` : schéma à jour, buckets, rapport figé de
Courbevoie comme rapport en vigueur (demande terminée), sans aucun appel réseau. Relançable.

Usage : ``uv run python scripts/essai/preparer.py``, puis lancer le serveur
(README, section Développement).
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion, fermer_pool
from bitumap.db.migrer import main as migrer


def main() -> None:
    migrer()
    client = stockage._client()
    r = reglages()
    for bucket in (r.bucket_rapports, r.bucket_cache, r.bucket_terrain):
        with contextlib.suppress(client.exceptions.BucketAlreadyOwnedByYou):
            client.create_bucket(Bucket=bucket)

    from tests.conftest import rapport_courbevoie

    empreinte = rapport_courbevoie()
    with connexion() as conn:
        conn.execute(
            "DELETE FROM demande d WHERE commune_insee = '92026' AND NOT EXISTS"
            " (SELECT 1 FROM demandeur_demande x WHERE x.demande_id = d.id)"
        )
        conn.execute(
            "INSERT INTO demande (commune_insee, commune_nom, empreinte, etat, termine_le)"
            " VALUES ('92026', 'Courbevoie', %s, 'terminee', now())",
            (empreinte,),
        )
    print(f"Rapport de Courbevoie prêt (empreinte {empreinte}).")


if __name__ == "__main__":
    try:
        main()
    finally:
        fermer_pool()
