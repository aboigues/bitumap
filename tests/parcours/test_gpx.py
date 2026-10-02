"""GPX 1.1 du parcours (006 T016, R5, FR-008, FR-012). Aucun validateur XSD n'est installé
(le plan exclut toute nouvelle dépendance) : contrôle de la structure du schéma GPX 1.1."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from bitumap.parcours import gpx

NS = {"g": "http://www.topografix.com/GPX/1/1"}


def _parcours() -> dict:
    visites = [
        {
            "ordre": 1,
            "point_id": "A36862",
            "rang": 1,
            "niveau": "P1a",
            "designation": "Hérold - Mairie · vers La Défense & <Nanterre>",
            "lon": 2.2521,
            "lat": 48.8973,
        },
        {
            "ordre": 2,
            "point_id": "A23742",
            "rang": 2,
            "niveau": "P1b",
            "designation": "Paix - Verdun",
            "lon": 2.2606,
            "lat": 48.9008,
        },
    ]
    return {
        "id": uuid.uuid4(),
        "compte_id": uuid.uuid4(),
        "commune_insee": "92026",
        "empreinte": "10540fa288a644c3",
        "depart_libelle": "2 Place De L'Hôtel De Ville 92400 Courbevoie",
        "depart_lon": 2.256307,
        "depart_lat": 48.895241,
        "cree_le": datetime(2026, 10, 1, tzinfo=UTC),
        "resultat": {
            "visites": visites,
            "troncons": [
                [[2.2563, 48.8952], [2.2521, 48.8973], [2.2606, 48.9008]],
                [[2.2606, 48.9008], [2.2563, 48.8952]],
            ],
            "resume": {"rapport_date": "2026-10-01", "nb_visites": 2},
        },
    }


def _lire(contenu: bytes) -> ET.Element:
    return ET.fromstring(contenu)  # noqa: S314 (GPX produit par le code testé)


def test_structure_gpx_1_1():
    racine = _lire(gpx.produire(_parcours(), "Courbevoie", "https://bitumap.example"))
    assert racine.tag == "{http://www.topografix.com/GPX/1/1}gpx"
    assert racine.get("version") == "1.1" and racine.get("creator") == "bitumap"
    enfants = [e.tag.split("}")[1] for e in racine]
    assert enfants == ["metadata", "wpt", "wpt", "wpt", "trk"]  # ordre du schéma
    for e in racine.iter():
        if e.get("lat") is not None:
            assert -90 <= float(e.get("lat")) <= 90 and -180 <= float(e.get("lon")) <= 180
    meta = [e.tag.split("}")[1] for e in racine.find("g:metadata", NS)]
    assert meta == ["name", "desc", "time"]


def test_points_de_passage_nommes_dans_l_ordre():
    racine = _lire(gpx.produire(_parcours(), "Courbevoie", "https://bitumap.example"))
    noms = [w.findtext("g:name", namespaces=NS) for w in racine.findall("g:wpt", NS)]
    assert noms == [
        "Départ",
        "1 · Critique · Hérold - Mairie · vers La Défense & <Nanterre>",
        "2 · Sérieux · Paix - Verdun",
    ]
    desc = racine.findall("g:wpt", NS)[1].findtext("g:desc", namespaces=NS)
    assert desc == (
        "Rang 1 · A36862 · fiche : https://bitumap.example/rapports/92026/10540fa288a644c3"
    )
    segments = racine.find("g:trk", NS).findall("g:trkseg", NS)
    assert [len(s.findall("g:trkpt", NS)) for s in segments] == [3, 2]


def test_metadonnees_et_aucune_donnee_de_compte():
    p = _parcours()
    contenu = gpx.produire(p, "Courbevoie", "https://bitumap.example", "2.0")
    texte = contenu.decode("utf-8")
    assert "Parcours de surveillance — Courbevoie" in texte
    assert "Rapport du 2026-10-01, méthode 2.0" in texte
    assert "IGN Géoplateforme" in texte and "OpenStreetMap" in texte and "IDFM" in texte
    assert str(p["compte_id"]) not in texte and "@" not in texte
    assert p["depart_libelle"] not in texte  # le départ n'est qu'un point « Départ »
    assert "&amp;" in texte and "&lt;Nanterre&gt;" in texte  # caractères échappés
