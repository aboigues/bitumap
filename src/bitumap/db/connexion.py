"""Pool de connexions psycopg ; chaque ``with connexion()`` est une transaction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from bitumap.config import reglages

_pool: ConnectionPool | None = None


def _obtenir_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            reglages().db_url.get_secret_value(),
            min_size=0,  # rien d'ouvert au repos (principe II)
            max_size=5,
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
