"""Outil d'évaluation de la méthode 2.0 (004 T036, R7) : relevés synthétiques au format de
l'export de 003, calcul simulé, aucun réseau."""

from __future__ import annotations

import json

import pytest

from bitumap.facteurs import chaleur
from bitumap.methode import evaluer
from bitumap.modele import Facteur, Point

COMMUNES = ("92001", "92002", "92003")


def _export(releves: list[tuple[str, str, str]]) -> dict:
    """GeoJSON au format de ``terrain.export.en_geojson`` : (point, niveau, date)."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [2.25, 48.9]},
                "properties": {
                    "releve": f"r{i}",
                    "point": point,
                    "niveau_constate": niveau,
                    "date": jour,
                    "designation": point,
                },
            }
            for i, (point, niveau, jour) in enumerate(releves)
        ],
    }


def _points(insee: str, prioritaires: set[str], soleil: float = 8.0) -> list[Point]:
    points = []
    for i in range(50):
        ident = f"{insee}-{i}"
        p = Point(ident, "arret", ident, 2.25, 48.9)
        p.groupe = "P1a" if ident in prioritaires else "P2"
        p.facteurs = [Facteur("ensoleillement", soleil, 1.0)]
        points.append(p)
    return points


def _calcul(meilleur: str | None = None, degrade: str | None = None):
    """v1 : 10 premiers points prioritaires ; v2 : 20 premiers ; un candidat ``meilleur``
    ajoute 5 points prioritaires partout, ``degrade`` en retire dans la première commune."""

    def calcul(insee, methode, retenus):
        n = 10 if methode == "1.2" else 20
        if meilleur in retenus:
            n += 5
        if degrade in retenus and insee == COMMUNES[0]:
            n -= 5
        return _points(insee, {f"{insee}-{i}" for i in range(n)})

    return calcul


def _releves(n_par_commune: int = 40, communes=COMMUNES) -> dict:
    # Points 0 à 29 orniérés (marqué ou grave), 30 et plus absents.
    lignes = []
    for insee in communes:
        for i in range(n_par_commune):
            niveau = ("marqué" if i % 2 else "grave") if i < 30 else "absent"
            lignes.append((f"{insee}-{i}", niveau, "2026-10-01T10:00:00"))
    return _export(lignes)


def _lire(tmp_path, donnees) -> dict:
    chemin = tmp_path / "releves.geojson"
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    return evaluer.lire_releves([chemin])


def test_lecture_export_geojson_et_csv_dernier_releve(tmp_path):
    releves = _lire(
        tmp_path,
        _export(
            [
                ("A1", "léger", "2026-09-01"),
                ("A1", "grave", "2026-09-20"),
                ("A2", "absent", "2026-09-02"),
            ]
        ),
    )
    assert releves["A1"].niveau == "grave" and releves["A1"].orniere
    assert not releves["A2"].orniere
    csv = tmp_path / "releves.csv"
    csv.write_text(
        "﻿releve;point;niveau_constate;date\r\nr1;A3;marqué;2026-09-03\r\n", encoding="utf-8"
    )
    assert evaluer.lire_releves([csv])["A3"].niveau == "marque"


def test_refus_sous_100_points_ou_3_communes(tmp_path):
    with pytest.raises(evaluer.RefusEvaluation, match="99 points relevés dans 3"):
        evaluer.evaluer(list(COMMUNES), _lire(tmp_path, _releves(33)), {}, _calcul())
    with pytest.raises(evaluer.RefusEvaluation, match="2 commune"):
        evaluer.evaluer(list(COMMUNES), _lire(tmp_path, _releves(50, COMMUNES[:2])), {}, _calcul())


def test_sc001_v1_contre_v2(tmp_path):
    e = evaluer.evaluer(list(COMMUNES), _lire(tmp_path, _releves()), {}, _calcul())
    v1, v2 = e.sc001()
    assert (v1, v2) == (pytest.approx(100 * 10 / 30), pytest.approx(100 * 20 / 30))


def test_apport_d_un_indicateur(tmp_path):
    temperature, mineralisation = chaleur.TEMPERATURE, chaleur.MINERALISATION
    e = evaluer.evaluer(
        list(COMMUNES),
        _lire(tmp_path, _releves()),
        {},
        _calcul(meilleur=temperature, degrade=mineralisation),
    )
    m = e.indicateur(temperature)
    assert m["retenu"] and m["ecart"] == pytest.approx(100 * 5 / 30)
    d = e.indicateur(mineralisation)
    assert not d["retenu"] and d["raison"] == f"dégrade la mesure à {COMMUNES[0]}"
    neutre = e.indicateur(chaleur.CONTEXTE)
    assert not neutre["retenu"] and neutre["raison"].startswith("apport inférieur")


def test_sc002_ecart_moyen(tmp_path):
    soleil = {f"{COMMUNES[0]}-{i}": 9.0 for i in range(30)}
    e = evaluer.evaluer(list(COMMUNES), _lire(tmp_path, _releves()), soleil, _calcul())
    assert e.sc002() == (30, pytest.approx(1.0))


def test_rapport_markdown_aux_sections_du_contrat(tmp_path):
    e = evaluer.evaluer(
        list(COMMUNES), _lire(tmp_path, _releves()), {}, _calcul(meilleur=chaleur.TEMPERATURE)
    )
    texte = evaluer.rapport_markdown(e)
    for section in (
        "Référence",
        "SC-001",
        "Indicateurs",
        "Ensoleillement (SC-002)",
        "Changements de niveau",
        "Décision",
    ):
        assert f"## {section}" in texte
    assert "à confirmer par le mainteneur" in texte
    assert f"`{chaleur.TEMPERATURE}`" in texte.split("## Décision")[1]
    assert "+33,3 points — **atteint**" in texte


def test_ligne_de_commande(tmp_path):
    chemin = tmp_path / "releves.geojson"
    chemin.write_text(json.dumps(_releves()), encoding="utf-8")
    sortie = tmp_path / "evaluation.md"
    code = evaluer.main(
        ["--releves", str(chemin), "--communes", *COMMUNES, "--sortie", str(sortie)], _calcul()
    )
    assert code == 0 and sortie.read_text(encoding="utf-8").startswith("# Évaluation")
    assert evaluer.main(["--releves", str(chemin), "--communes", "92001"], _calcul()) == 2
