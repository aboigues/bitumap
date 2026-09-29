"""Rendu du rapport (T067, contracts/report-bundle.md) sur Courbevoie, sans réseau.

Autonome (FR-020), sections dans l'ordre du contrat, type de route pour 100 % des points,
sources complètes (principe III), résultats IA marqués « à confirmer » (FR-019).
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from functools import cache
from html.parser import HTMLParser
from pathlib import Path

import pytest

from bitumap.calcul import calculer_commune
from bitumap.journal import JournalGeneration
from bitumap.modele import Facteur
from bitumap.rapport import rendu
from bitumap.score.methode import VERSION_METHODE
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"
CLASSEMENTS = {
    "autoroute",
    "nationale",
    "départementale",
    "communale",
    "communale_presumee",
    "privee",
    "indetermine",
}


@cache
def _resultat():
    return calculer_commune(FournisseurFige(FIXTURES, "92026"), "Courbevoie")


@pytest.fixture(scope="module")
def rapport():
    resultat = copy.deepcopy(_resultat())
    premier = resultat.points[0]
    premier.facteurs = [f for f in premier.facteurs if f.nom != "age_enrobe"]
    premier.facteurs.append(
        Facteur(
            "age_enrobe",
            "5–12 ans",
            0.85,
            provenance="ia",
            statut="a_confirmer",
            explication="Réfection visible entre deux prises de vue",
            modele="modele-de-test",
            date="2026-09-29",
        )
    )
    fichiers = rendu.rendre(resultat, JournalGeneration("92026", VERSION_METHODE))
    html = fichiers["rapport.html"][0].decode()
    analyse = _Ressources()
    analyse.feed(html)
    donnees = json.loads(next(t for a, t in analyse.scripts if a.get("id") == "donnees"))
    return {
        "analyse": analyse,
        "resultat": resultat,
        "fichiers": fichiers,
        "html": html,
        "donnees": donnees,
        "premier": premier.id,
    }


class _Ressources(HTMLParser):
    """Analyse le HTML comme un navigateur (balises insensibles à la casse) : ressources
    chargées automatiquement, liens cliquables <a>, balises et contenu des <script>."""

    ATTRIBUTS = frozenset({"src", "href", "srcset", "poster", "data", "action", "xlink:href"})

    def __init__(self):
        super().__init__()
        self.chargees: list[str] = []
        self.liens: list[str] = []
        self.balises: set[str] = set()
        self.scripts: list[tuple[dict, str]] = []
        self._script: dict | None = None

    def handle_starttag(self, tag, attrs):
        self.balises.add(tag)
        for nom, valeur in attrs:
            if nom in self.ATTRIBUTS and valeur:
                (self.liens if tag == "a" else self.chargees).append(f"{tag} {nom}={valeur}")
        if tag == "script":
            self._script = dict(attrs)
            self.scripts.append((self._script, ""))

    def handle_data(self, data):
        if self._script is not None:
            attrs, texte = self.scripts[-1]
            self.scripts[-1] = (attrs, texte + data)

    def handle_endtag(self, tag):
        if tag == "script":
            self._script = None


def test_aucune_ressource_externe(rapport):
    analyse = rapport["analyse"]
    assert analyse.chargees == []  # ni script, ni style, ni image, ni police externes
    assert analyse.liens  # les liens cliquables (sources, photos) restent permis
    assert not re.search(r"@import|url\(\s*['\"]?(https?:)?//", rapport["html"])
    assert not analyse.balises & {"link", "iframe", "object", "embed", "base"}


def test_script_conforme_a_la_csp(rapport):
    executables = [t for a, t in rapport["analyse"].scripts if a.get("type") != "application/json"]
    assert len(executables) == 1  # le seul script exécutable, en ligne
    empreinte = base64.b64encode(hashlib.sha256(executables[0].encode()).digest()).decode()
    assert f"'sha256-{empreinte}'" in rendu.CSP_RAPPORT


def test_sections_dans_l_ordre_du_contrat(rapport):
    html = rapport["html"]
    reperes = [
        "Courbevoie</h1>",  # 1. en-tête
        "ne mesure pas l'état réel de la chaussée",  # 1. avertissement FR-022
        'aria-label="Synthèse"',  # 2. synthèse
        'aria-label="Types de route"',
        "<svg",  # 3. carte
        # 3 à 5 partagent une grille : carte et fiche (sous la carte) à gauche, liste filtrable
        # à droite ; la fiche est remplie depuis <template id="gabarit-fiche">.
        'id="fiche"',
        'data-filtre="route"',
        f"Méthode {VERSION_METHODE}",  # 6. méthode
        "Limites connues",
        "<h2>Sources</h2>",  # 7. sources
    ]
    positions = [html.find(r) for r in reperes]
    assert -1 not in positions, [r for r, p in zip(reperes, positions, strict=True) if p < 0]
    assert positions == sorted(positions)


def test_lisible_sur_telephone(rapport):
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in rapport["html"]
    assert "@media" in rapport["html"]


def test_type_de_route_pour_tous_les_points(rapport):
    points = rapport["donnees"]["points"]
    assert points and all(p["route"]["classement"] in CLASSEMENTS for p in points)
    geojson = json.loads(rapport["fichiers"]["points.geojson"][0])
    assert len(geojson["features"]) == len(points)
    for f in geojson["features"]:
        assert f["properties"]["route"]["classement"] in CLASSEMENTS
        assert f["geometry"]["type"] == "Point"
    # chaque type de route présent est proposé dans le filtre
    for classement in {p["route"]["classement"] for p in points}:
        assert f'<option value="{classement}">' in rapport["html"]


def test_sources_avec_licence_lien_et_date(rapport):
    sources = json.loads(rapport["fichiers"]["sources.json"][0])
    assert sources
    for s in sources:
        assert s["licence"] and s["url"].startswith("https://") and s["date_extraction"], s
        assert f'href="{s["url"]}"' in rapport["html"]


def test_resultats_ia_marques_a_confirmer(rapport):
    point = next(p for p in rapport["donnees"]["points"] if p["id"] == rapport["premier"])
    age = next(f for f in point["facteurs"] if f["nom"] == "age_enrobe")
    assert age["provenance"] == "ia" and age["statut"] == "a_confirmer"
    assert age["modele"] and age["date"]
    assert "[IA, à confirmer]" in rapport["html"]  # étiquette posée par le script de la fiche
    assert "marqués « à confirmer »" in rapport["html"]
    assert 'id="gabarit-fiche"' in rapport["html"]


def test_direction_et_identifiant_du_quai_affiches(rapport):
    html = rapport["html"]
    attendu = "Paix - Verdun · vers La Défense, Porte de Saint-Cloud · Boulevard Aristide Briand"
    assert attendu in html  # liste
    assert f"<title>{attendu}" in html.replace("&#x27;", "'")  # infobulle de la carte
    assert "quai IDFM 36807" in html
    point = next(p for p in rapport["donnees"]["points"] if p["id"] == "A36807")
    assert point["designation"].startswith(attendu)  # fiche (remplie par le script)
    assert point["identifiant"] == "quai IDFM 36807"
    assert "p.designation" in html and "p.identifiant" in html


def test_sous_groupes_du_p1(rapport):
    html = rapport["html"]
    for groupe in ("P1a", "P1b", "P1c"):
        assert f"<option>{groupe}</option>" in html
        assert f'class="pastille {groupe}"' in html
    points = rapport["donnees"]["points"]
    p1 = [p for p in points if p["priorite"] == "P1"]
    assert {p["groupe"] for p in p1} == {"P1a", "P1b", "P1c"}
    assert "p.groupe === filtres.priorite" in html


def test_liens_panoramax_vers_la_visionneuse(rapport):
    photos = [p["panoramax"] for p in rapport["donnees"]["points"] if p["panoramax"]]
    assert photos
    for photo in photos:  # panoramax.fr est le site du projet, pas une visionneuse
        assert photo["url"] == f"https://api.panoramax.xyz/#focus=pic&pic={photo['id']}"
