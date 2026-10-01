"""Cohérence niveau / profondeur (003 FR-005b, R11, T013)."""

import pytest

from bitumap.db import connexion
from bitumap.terrain.depot import incoherence
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain.aides import deposer


@pytest.mark.parametrize(
    ("niveau", "mm", "attendu"),
    [
        ("leger", 5, None),
        ("leger", 10, "marque"),
        ("marque", 10, None),
        ("marque", 20, None),
        ("marque", 21, "grave"),
        ("grave", 25, None),
        ("grave", 9, "leger"),
        ("absent", 4, None),
        ("absent", 12, "marque"),
        ("leger", None, None),
    ],
)
def test_reperes(niveau, mm, attendu):
    assert incoherence(niveau, mm) == attendu


def test_avertissement_sans_enregistrement_puis_confirmation(client, courriels, s3):
    rapport_courbevoie()
    csrf = connecter(client, courriels)
    releve_id, reponse = deposer(
        client, csrf, niveau="leger", profondeur_mm=25, instrument="règle et cale"
    )
    assert reponse.status_code == 200
    assert reponse.json()["avertissement"] == "mesure_incoherente"
    assert reponse.json()["niveau_suggere"] == "grave"
    with connexion() as conn:
        assert conn.execute("SELECT count(*) AS n FROM releve").fetchone()["n"] == 0

    _, confirme = deposer(
        client,
        csrf,
        releve_id=releve_id,
        niveau="leger",
        profondeur_mm=25,
        instrument="règle et cale",
        confirme_malgre_incoherence=True,
    )
    assert confirme.status_code == 201
    with connexion() as conn:
        v = conn.execute("SELECT * FROM releve_version").fetchone()
    assert v["niveau"] == "leger" and v["incoherence_confirmee"] is True
