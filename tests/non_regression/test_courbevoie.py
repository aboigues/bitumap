"""Non-régression Courbevoie face au prototype (SC-003, SC-004), sans réseau.

Données figées par ``tools/figer_fixtures.py`` ; prototype : docs/reference.

Comparaison équitable : le prototype appliquait l'âge de l'enrobé (IA) avant de fixer ses
P1 ; on le retire de ses scores pour comparer à notre classement hors IA (priorités figées
avant l'IA, analyse F1). Les carrefours sont appariés par position (identifiants différents).
"""

from __future__ import annotations

import json
import math
import re
from functools import cache
from pathlib import Path

import pytest

from bitumap.calcul import calculer_commune
from bitumap.sources.fournisseur import FournisseurFige

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "tests" / "fixtures" / "courbevoie"
PROTOTYPE = RACINE / "docs" / "reference" / "prototype-courbevoie-v2.html"

# Mesuré le 2026-09-28 : 74 % (23/31). Les 8 P1 non retrouvés sont expliqués ci-dessous.
# L'objectif SC-003 (80 %) n'est pas atteint : écart accepté par le mainteneur le 2026-09-28
# (ensoleillement refondu en 004).
SEUIL_P1 = 0.74
ECARTS_EXPLIQUES = {
    "A23729": "ensoleillement (7,5 h contre 8,5 h), score à 96 % du seuil P1",
    "A25835": "îlot de chaleur à plus de 50 m, ensoleillement (11 h contre 9,6 h)",
    "A24336": "à la frontière (98 % du seuil P1), effet cumulé des écarts d'ensoleillement",
    "A18789": "à la frontière (99 % du seuil P1)",
    "F23": "charge du carrefour (605 contre 242 bus/j) et ombre des tours de La Défense",
    "A420557": "carrefour à feux voisin non repéré à moins de 40 m (facteur feu absent)",
    "A36806": "ensoleillement (7 h contre 8,1 h)",
    "A420570": "à la frontière (100 % du seuil P1, rang 32), ensoleillement (4,5 h contre 5,2 h)",
}


@cache
def prototype() -> list[dict]:
    html = PROTOTYPE.read_text(encoding="utf-8")
    return json.loads(re.search(r"const D = (\{.*?\});\s*\n", html, re.S).group(1))["points"]


@cache
def resultat():
    return calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")


def _distance_m(a, b) -> float:
    return math.hypot((a[0] - b[0]) * 73_300, (a[1] - b[1]) * 111_200)


def _p1_prototype_hors_ia() -> list[dict]:
    def score(p):
        f = " ".join(p["facteurs"])
        return p["score"] / (0.85 if "(×0,85)" in f else 1) / (1.05 if "(×1,05)" in f else 1)

    tri = sorted(prototype(), key=lambda p: -score(p))
    return tri[: math.ceil(len(tri) * 0.2)]


def _apparier(p: dict):
    points = resultat().points
    if p["id"].startswith("A"):
        return next((n for n in points if n.id == p["id"]), None)
    candidat = min(
        (n for n in points if n.type != "arret"),
        key=lambda n: _distance_m((n.lon, n.lat), (p["lon"], p["lat"])),
    )
    return (
        candidat if _distance_m((candidat.lon, candidat.lat), (p["lon"], p["lat"])) < 40 else None
    )


def test_memes_arrets_que_le_prototype():
    nous = {p.id for p in resultat().points if p.type == "arret"}
    proto = {p["id"] for p in prototype() if p["id"].startswith("A")}
    assert nous == proto


def test_offre_de_bus_identique():
    proto = {p["id"]: p for p in prototype()}
    for p in resultat().points:
        if p.type == "arret":
            assert round(p.bus_jour) == pytest.approx(proto[p.id]["bus_jour"], abs=1), p.id


def test_pentes_identiques():
    proto = {p["id"]: p for p in prototype()}
    for p in resultat().points:
        if p.type == "arret" and proto[p.id]["pente"] is not None:
            assert p.facteur("pente").valeur == pytest.approx(proto[p.id]["pente"], abs=0.2), p.id


def test_nombre_de_carrefours_et_giratoires_proche():
    types = [p.type for p in resultat().points]
    assert abs(types.count("feu") - 57) <= 3
    assert types.count("giratoire") == 7


def test_sc003_p1_du_prototype_retrouves():
    p1 = _p1_prototype_hors_ia()
    manquants = [p["id"] for p in p1 if not ((n := _apparier(p)) and n.priorite == "P1")]
    taux = 1 - len(manquants) / len(p1)
    assert taux >= SEUIL_P1, f"{taux:.0%} < {SEUIL_P1:.0%} ; manquants : {manquants}"
    inexpliques = [m for m in manquants if m not in ECARTS_EXPLIQUES]
    assert not inexpliques, f"écarts non expliqués : {inexpliques}"


def test_sc004_classement_deterministe():
    a = calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")
    b = calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")
    assert [(p.id, p.rang, p.priorite, p.score) for p in a.points] == [
        (p.id, p.rang, p.priorite, p.score) for p in b.points
    ]


def test_tous_les_points_ont_un_type_de_route():
    assert all(p.route.classement for p in resultat().points)


def test_sources_avec_licence_url_et_date():
    for prov in resultat().provenances:
        assert prov.licence and prov.url.startswith("https://") and prov.date_extraction
