"""Témoins de la file (T096) et migrations par le job (T097)."""

import importlib
from datetime import UTC, datetime

import pytest

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.lot import __main__ as job
from bitumap.lot import temoin
from tests.conftest import connecter, preuve

HORS_PASSAGE = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


def _demande(etat="en_file", empreinte="e1") -> str:
    with connexion() as conn:
        return str(
            conn.execute(
                "INSERT INTO demande (commune_insee, commune_nom, empreinte, etat)"
                " VALUES ('92026', 'Courbevoie', %s, %s) RETURNING id",
                (empreinte, etat),
            ).fetchone()["id"]
        )


def _sans_base(monkeypatch):
    """Toute connexion à la base, migration ou lot fait échouer le test."""

    def interdit(*_a, **_k):
        raise AssertionError("connexion à la base inattendue")

    module_connexion = importlib.import_module("bitumap.db.connexion")
    monkeypatch.setattr(module_connexion, "_obtenir_pool", interdit)
    monkeypatch.setattr(job, "migrer", interdit)
    monkeypatch.setattr(job, "executer", interdit)


def test_mise_en_file_depose_un_temoin(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    client.post(
        "/demandes",
        data={"insee": "92026", "csrf": csrf, "altcha": preuve(client)},
        follow_redirects=False,
    )
    with connexion() as conn:
        demande = str(conn.execute("SELECT id FROM demande").fetchone()["id"])
    assert temoin.en_attente() == [demande]


def test_sans_temoin_pas_de_mise_en_file(client, courriels, territoire, s3, monkeypatch):
    def panne(_demande_id):
        raise OSError("stockage indisponible")

    monkeypatch.setattr(temoin, "signaler", panne)
    csrf = connecter(client, courriels)
    with pytest.raises(OSError):  # le client de test relance l'erreur au lieu du 500
        client.post(
            "/demandes",
            data={"insee": "92026", "csrf": csrf, "altcha": preuve(client)},
            follow_redirects=False,
        )
    with connexion() as conn:  # transaction annulée : ni demande ni quota consommé
        assert conn.execute("SELECT count(*) AS n FROM demande").fetchone()["n"] == 0


def test_file_vide_sans_connexion_a_la_base(s3, monkeypatch):
    temoin.noter_schema()
    _sans_base(monkeypatch)
    assert job.lancer(maintenant=HORS_PASSAGE) is None


@pytest.mark.parametrize(
    ("heure", "minute", "attendu"), [(2, 0, True), (2, 14, True), (2, 15, False), (3, 5, False)]
)
def test_passage_quotidien(heure, minute, attendu):
    assert reglages().lot_heure_quotidienne_utc == 2
    maintenant = datetime(2026, 10, 6, heure, minute, tzinfo=UTC)
    assert temoin.passage_quotidien(maintenant) is attendu


def test_passage_quotidien_ouvre_la_base_sans_demande(base, s3, monkeypatch):
    temoin.noter_schema()
    appels = []
    monkeypatch.setattr(job, "executer", lambda *_a, **_k: appels.append(1) or [])
    assert job.lancer(maintenant=datetime(2026, 10, 6, 2, 0, tzinfo=UTC)) == []
    assert appels == [1]


def test_nouvelle_migration_ouvre_la_base_et_est_notee(base, s3, monkeypatch):
    appels = []
    monkeypatch.setattr(job, "executer", lambda *_a, **_k: appels.append(1) or [])
    assert not temoin.schema_note()  # image neuve : dernière migration jamais notée
    job.lancer(maintenant=HORS_PASSAGE)
    assert appels == [1] and temoin.schema_note()
    _sans_base(monkeypatch)
    assert job.lancer(maintenant=HORS_PASSAGE) is None  # notée : plus de réveil


def test_lot_retire_les_temoins_des_demandes_finies(base, s3, monkeypatch):
    temoin.noter_schema()
    finie, en_file = _demande(empreinte="e1"), _demande(empreinte="e2")
    for demande in (finie, en_file, "inconnue"):
        temoin.signaler(demande)

    def lot(*_a, **_k):
        with connexion() as conn:
            conn.execute("UPDATE demande SET etat = 'terminee' WHERE id = %s", (finie,))
        temoin.signaler(_demande(empreinte="e3"))  # mise en file pendant le lot
        return []

    monkeypatch.setattr(job, "executer", lot)
    job.lancer(maintenant=HORS_PASSAGE)
    restants = set(temoin.en_attente())
    assert finie not in restants and "inconnue" not in restants
    assert en_file in restants and len(restants) == 2  # demande encore en file + nouvelle


def test_lot_interrompu_garde_les_temoins(base, s3, monkeypatch):
    temoin.noter_schema()
    demande = _demande()
    temoin.signaler(demande)

    def panne(*_a, **_k):
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(job, "executer", panne)
    assert job.main([]) == 1
    assert temoin.en_attente() == [demande]


def test_lancement_complet_force_l_ouverture(base, s3, monkeypatch):
    temoin.noter_schema()
    appels = []
    monkeypatch.setattr(job, "executer", lambda *_a, **_k: appels.append(1) or [])
    job.lancer(complet=True, maintenant=HORS_PASSAGE)
    assert appels == [1]


def test_temoins_dans_le_bucket_du_cache(s3):
    temoin.signaler("abc")
    assert stockage.lister(reglages().bucket_cache, "file/") == ["file/abc"]


def test_le_job_ferme_le_pool_avant_de_sortir(base, s3, monkeypatch):
    module_connexion = importlib.import_module("bitumap.db.connexion")
    monkeypatch.setattr(job, "executer", lambda *_a, **_k: [])
    assert job.main(["--complet"]) == 0
    assert module_connexion._pool is None  # LL-022
