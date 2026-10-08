"""Sélection de la méthode et empreinte (004 T012, R8) : la 1.2 reste inchangée."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from bitumap.config import Reglages, reglages
from bitumap.lot import versions
from bitumap.lot.empreinte import empreinte
from bitumap.score import methode

SOURCES = {"idfm": date(2026, 9, 1), "osm": date(2026, 9, 28), "chaleur": date(2022, 1, 1)}


def test_methode_par_defaut_1_2():
    assert Reglages().methode == "1.2"
    assert methode.version_appliquee() == methode.VERSION_METHODE == "1.2"


def test_methode_inconnue_refusee():
    with pytest.raises(ValidationError):
        Reglages(methode="3.0")


def test_empreinte_1_2_inchangee():
    r = reglages()
    attendue = empreinte("92026", "1.2", SOURCES, r.ia_modele, r.ia_version_prompt)
    assert versions.empreinte_pour("92026", SOURCES) == attendue


def test_empreinte_2_0_porte_version_et_ete(monkeypatch):
    une_2 = versions.empreinte_pour("92026", SOURCES)
    monkeypatch.setattr(reglages(), "methode", "2.0")
    monkeypatch.setattr(reglages(), "ete_reference", 2026)
    assert methode.version_appliquee() == "2.0"
    ete_2026 = versions.empreinte_pour("92026", SOURCES)
    assert ete_2026 != une_2
    assert versions.empreinte_pour("92026", SOURCES) == ete_2026  # stable
    monkeypatch.setattr(reglages(), "ete_reference", 2027)
    assert versions.empreinte_pour("92026", SOURCES) != ete_2026  # nouvel été (FR-007)


@pytest.mark.parametrize(
    ("jour", "ete"),
    [(date(2026, 9, 30), 2025), (date(2026, 10, 1), 2026), (date(2027, 3, 1), 2026)],
)
def test_ete_de_reference_par_defaut(monkeypatch, jour, ete):
    # Dernier été complet dont les mesures sont publiées : à partir d'octobre.
    monkeypatch.setattr(reglages(), "ete_reference", None)
    assert methode.ete_reference(jour) == ete


def test_ete_de_reference_fixe(monkeypatch):
    monkeypatch.setattr(reglages(), "ete_reference", 2024)
    assert methode.ete_reference(date(2026, 10, 1)) == 2024


def test_revision_du_calcul_rend_les_rapports_obsoletes(monkeypatch):
    # Un correctif du calcul doit invalider les rapports en cache (30 jours sinon).
    from bitumap.lot import empreinte as module

    avant = versions.empreinte_pour("92026", SOURCES)
    monkeypatch.setattr(module, "REVISION_CALCUL", module.REVISION_CALCUL + 1)
    assert versions.empreinte_pour("92026", SOURCES) != avant
