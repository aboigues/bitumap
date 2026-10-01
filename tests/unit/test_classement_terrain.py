"""Classement corrigé par le terrain (004 T046, R9, FR-016 à FR-018) : fonctions pures, sans
base."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from bitumap.terrain import classement


@pytest.mark.parametrize(
    ("ete", "annee", "attendu"),
    [(2026, 2026, 0.5), (2026, 2020, 0.8), (2026, 2016, 1.0), (2026, 2001, 1.0), (2026, 2027, 0.5)],
)
def test_effet_degressif_sur_10_ans(ete, annee, attendu):
    assert classement.effet(ete, annee) == pytest.approx(attendu)


def _releve(point, cree_le, niveau="absent", annee=None, source=None, **autres):
    return {
        "point_id": point,
        "cree_le": datetime.fromisoformat(cree_le),
        "niveau": niveau,
        "annee_refection": annee,
        "source_refection": source,
        **autres,
    }


def test_seules_les_sources_confirmees_comptent():
    r = classement.refections_depuis(
        [
            _releve("A1", "2026-09-01", annee=2020, source="constatee"),
            _releve("A2", "2026-09-01", annee=2021, source="services_techniques"),
            _releve("A3", "2026-09-01", annee=2022, source="estimee_agent"),
            _releve("A4", "2026-09-01"),
        ]
    )
    assert set(r) == {"A1", "A2"}
    assert (r["A1"]["annee_refection"], r["A1"]["source_refection"]) == (2020, "constatee")


def test_plus_recente_annee_confirmee_et_dernier_releve():
    r = classement.refections_depuis(
        [
            _releve("A1", "2026-09-20", niveau="leger"),
            _releve("A1", "2026-08-01", annee=2018, source="constatee"),
            _releve("A1", "2026-09-01", annee=2021, source="services_techniques"),
            _releve("A1", "2026-09-05", annee=2023, source="estimee_agent"),
        ]
    )["A1"]
    assert (r["annee_refection"], r["source_refection"]) == (2021, "services_techniques")
    assert (r["dernier_niveau"], r["dernier_annee"]) == ("leger", 2026)


def _geojson(*points) -> dict:
    """Points d'un rapport : (id, effets des facteurs)."""
    return {
        "type": "FeatureCollection",
        "ete_reference": {"annee": 2026},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [2.25, 48.9]},
                "properties": {
                    "id": ident,
                    "type": "arret",
                    "nom": ident,
                    "facteurs": [{"nom": "charge", "valeur": None, "effet": e} for e in effets],
                },
            }
            for ident, effets in points
        ],
    }


# 10 points : A0 le plus exposé (score 10) … A9 le moins (score 1).
POINTS = _geojson(*[(f"A{i}", [10.0 - i]) for i in range(10)])


def _refection(annee, dernier_niveau="absent", dernier_annee=2026, source="constatee"):
    return {
        "annee_refection": annee,
        "source_refection": source,
        "dernier_niveau": dernier_niveau,
        "dernier_annee": dernier_annee,
    }


def test_point_refait_descend_sans_toucher_aux_autres_scores():
    resultat = classement.corriger(POINTS, {"A0": _refection(2026)}, 2026)
    a0 = resultat["points"]["A0"]
    assert a0 == {
        "annee_refection": 2026,
        "source_refection": "constatee",
        "effet": 0.5,
        "annule": False,
        "motif": None,
        "rang": 5,  # score 5 : après A1 (9) … A4 (6) ; ex aequo avec A5, « A0 » passe avant
        "groupe": "P2",
    }
    assert resultat["nb_points_corriges"] == 1
    rangs = {c["id"]: c["rang"] for c in resultat["classement"]}
    assert rangs["A1"] == 1 and len(rangs) == 10
    assert set(resultat["points"]) == {"A0"}  # point sans réfection confirmée : absent


def test_meme_regles_que_l_estime_sans_refection():
    """Sans réfection, le classement « corrigé » est celui du rapport (score.combinaison)."""
    resultat = classement.corriger(POINTS, {}, 2026)
    assert [c["id"] for c in resultat["classement"]] == [f"A{i}" for i in range(10)]
    assert [c["groupe"] for c in resultat["classement"]][:3] == ["P1a", "P1b", "P2"]
    assert resultat["nb_points_corriges"] == 0 and resultat["points"] == {}


def test_annulation_si_ornierage_constate_apres_les_travaux():
    resultat = classement.corriger(POINTS, {"A0": _refection(2020, "marque", 2026)}, 2026)
    a0 = resultat["points"]["A0"]
    assert (a0["effet"], a0["annule"], a0["rang"]) == (1.0, True, 1)
    assert a0["motif"] == "réfection sans effet : orniérage constaté après les travaux"
    assert resultat["nb_points_corriges"] == 0


def test_ornierage_constate_avant_les_travaux_n_annule_pas():
    resultat = classement.corriger(POINTS, {"A0": _refection(2026, "grave", 2025)}, 2026)
    assert resultat["points"]["A0"]["effet"] == 0.5 and not resultat["points"]["A0"]["annule"]


def test_aucune_donnee_personnelle_et_determinisme():
    refections = classement.refections_depuis(
        [
            _releve(
                "A0",
                "2026-09-01",
                annee=2020,
                source="constatee",
                email="a@exemple.fr",
                auteur="agent a…@exemple.fr",
                compte_id="c1",
                lon=2.2,
                lat=48.9,
            )
        ]
    )
    premier = classement.corriger(POINTS, refections, 2026)
    texte = json.dumps(premier, ensure_ascii=False)
    assert "exemple.fr" not in texte and "auteur" not in texte and "lon" not in texte
    assert classement.corriger(POINTS, refections, 2026) == premier
