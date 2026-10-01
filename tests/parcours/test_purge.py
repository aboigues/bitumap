"""Table des parcours (006 T001, T003) : contraintes du modèle, purge à 24 h (SC-006)."""

from __future__ import annotations

from datetime import timedelta

import psycopg
import pytest
from psycopg.types.json import Jsonb

from bitumap.db import connexion
from bitumap.db.purge import purger

INSERTION = (
    "INSERT INTO parcours (compte_id, commune_insee, empreinte, depart_libelle, depart_lon,"
    " depart_lat, niveaux, mode, duree_max_min, arret_min, resultat, expire_le)"
    " VALUES (%(compte)s, '92026', 'e', %(libelle)s, 2.25, 48.9, %(niveaux)s, %(mode)s,"
    " %(duree)s, 5, %(resultat)s, now() + %(dans)s)"
)


def _compte(conn) -> str:
    return conn.execute(
        "INSERT INTO compte (email) VALUES ('agent@exemple.fr') RETURNING id"
    ).fetchone()["id"]


def _valeurs(compte, **autres) -> dict:
    return {
        "compte": compte,
        "libelle": "2 Place De L'Hôtel De Ville 92400 Courbevoie",
        "niveaux": ["P1a"],
        "mode": "voiture",
        "duree": 180,
        "resultat": Jsonb({}),
        "dans": timedelta(hours=24),
        **autres,
    }


def test_parcours_expires_purges(base):
    with connexion() as conn:
        compte = _compte(conn)
        conn.execute(INSERTION, _valeurs(compte, dans=timedelta(minutes=-1)))
        conn.execute(INSERTION, _valeurs(compte, dans=timedelta(hours=23)))
    assert purger()["parcours"] == 1
    with connexion() as conn:
        assert conn.execute("SELECT count(*) AS n FROM parcours").fetchone()["n"] == 1


@pytest.mark.parametrize(
    "erreur",
    [{"mode": "velo"}, {"duree": 600}, {"duree": 10}, {"niveaux": ["P9"]}, {"niveaux": []}],
)
def test_contraintes_du_modele(base, erreur):
    with connexion() as conn:
        compte = _compte(conn)
    with pytest.raises(psycopg.errors.CheckViolation), connexion() as conn:
        conn.execute(INSERTION, _valeurs(compte, **erreur))
