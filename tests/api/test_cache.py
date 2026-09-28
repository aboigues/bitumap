"""Validité du cache des rapports (FR-008, T090)."""

from datetime import UTC, date, datetime, timedelta

from bitumap.api import demandes
from bitumap.config import reglages
from bitumap.lot import versions
from tests.lot.aides import executer_lot, regional_fige


def _produire(base):
    from tests.lot.test_lot import _demande

    _demande()
    executer_lot()


def test_rapport_a_jour_reutilise(base, s3):
    _produire(base)
    assert demandes.rapport_valide("92026") == versions.empreinte_courante("92026")


def test_rapport_trop_ancien_non_reutilise(base, s3, monkeypatch):
    _produire(base)
    vieux = datetime.now(UTC) - timedelta(days=31)
    monkeypatch.setattr(demandes.stockage, "date_rapport", lambda insee, e: vieux)
    assert demandes.rapport_valide("92026") is None


def test_nouvelle_version_de_source(base, s3):
    _produire(base)
    regional_fige(None)
    versions.enregistrer("osm", date(2026, 10, 4))  # nouvel extrait OSM
    assert demandes.rapport_valide("92026") is None


def test_changement_de_modele_ia(base, s3, monkeypatch):
    _produire(base)
    monkeypatch.setattr(reglages(), "ia_modele", "qwen3.8-27b")
    assert demandes.rapport_valide("92026") is None
