"""Pool de connexions face à la mise en veille de la base Serverless (LL-034).

La base coupe ses connexions après 5 min sans requête ; le pool ne doit jamais donner une
connexion coupée à une requête (erreur 500 à la première page après une inactivité).
"""

import psycopg

from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.db.connexion import MAX_IDLE_S, _obtenir_pool


def _couper(pid: int) -> None:
    """Coupe la connexion ``pid`` côté serveur, comme le fait la mise en veille."""
    url = reglages().db_url.get_secret_value()
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(%s)", (pid,))


def test_connexion_coupee_par_la_base_remplacee(base):
    with connexion() as conn:
        pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    _couper(pid)

    with connexion() as conn:  # même connexion rendue par le pool : elle doit être vérifiée
        nouveau = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    assert nouveau != pid


def test_connexions_inutilisees_fermees_avant_la_veille():
    # Nettoyage toutes les max_idle secondes : au plus 2 × max_idle d'inactivité < 5 min.
    assert 2 * MAX_IDLE_S < 5 * 60
    assert _obtenir_pool().max_idle == MAX_IDLE_S
