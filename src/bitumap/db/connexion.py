"""Pool de connexions psycopg ; chaque ``with connexion()`` est une transaction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from bitumap.config import reglages

_pool: ConnectionPool | None = None
MAX_IDLE_S = 120.0


def _obtenir_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            reglages().db_url.get_secret_value(),
            min_size=0,  # rien d'ouvert au repos (principe II)
            max_size=5,
            # La base Serverless coupe ses connexions à sa mise en veille (5 min sans requête) :
            # connexion vérifiée avant d'être donnée, remplacée si elle est coupée (LL-034) ;
            # connexions inutilisées fermées avant la veille (contrôle toutes les max_idle s,
            # donc au plus 2 × max_idle = 4 min d'inactivité).
            check=ConnectionPool.check_connection,
            max_idle=MAX_IDLE_S,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def connexion() -> Iterator[psycopg.Connection]:
    """Connexion transactionnelle : validée en sortie normale, annulée sur exception."""
    with _obtenir_pool().connection() as conn, conn.transaction():
        yield conn


def fermer_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
