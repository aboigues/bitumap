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
    libelles = {"P1a": "Critique", "P1b": "Sérieux", "P1c": "Important"}
    libelles |= {"P2": "À surveiller", "P3": "Supportable"}
    for code, libelle in libelles.items():  # codes internes, libellés affichés (revue #17)
        assert f'<option value="{code}">{libelle}</option>' in html
        assert f'class="pastille {code}">{libelle}</span>' in html
    assert '<option value="P1">Critique à important</option>' in html
    assert ">P1a<" not in html and ">P2<" not in html
    points = rapport["donnees"]["points"]
    p1 = [p for p in points if p["priorite"] == "P1"]
    assert {p["groupe"] for p in p1} == {"P1a", "P1b", "P1c"}
    assert {p["groupe_libelle"] for p in p1} == {"Critique", "Sérieux", "Important"}
    assert "p.groupe === filtres.priorite" in html


def test_liens_panoramax_vers_la_visionneuse(rapport):
    photos = [p["panoramax"] for p in rapport["donnees"]["points"] if p["panoramax"]]
    assert photos
    for photo in photos:  # panoramax.fr est le site du projet, pas une visionneuse
        assert photo["url"] == f"https://api.panoramax.xyz/#focus=pic&pic={photo['id']}"


def test_cinq_couleurs_de_niveau_distinctes(rapport):
    """Revue de la PR #17 : une couleur par niveau, dans la synthèse, les pastilles et la
    carte, pour chacun des deux thèmes."""
    html = rapport["html"]
    for theme in re.findall(r"--P1a:[^}]*", html):
        couleurs = dict(re.findall(r"--(P1a|P1b|P1c|P2|P3):(#[0-9a-f]{6})", theme))
        assert len(couleurs) == 5 and len(set(couleurs.values())) == 5, couleurs
    assert len(re.findall(r"--P1a:", html)) == 2  # thème clair et thème sombre
    for code in ("P1a", "P1b", "P1c", "P2", "P3"):
        assert f'class="chiffre niveau {code}"' in html
    assert 'fill="var(--P1a)"' in html


def test_lien_photos_aeriennes(rapport):
    # Vérification hors Panoramax : comparaison IGN « Remonter le temps », aujourd'hui (couche
    # 10) contre 2016-2020 (couche 11) ; format vérifié dans un navigateur (LL-007).
    assert rendu.lien_photos_aeriennes(2.255795179, 48.89694812) == (
        "https://remonterletemps.ign.fr/comparer/?lon=2.255795&lat=48.896948&z=19"
        "&layer1=10&layer2=11&mode=split-h"
    )
    points = rapport["donnees"]["points"]
    assert all(
        p["photos_aeriennes"].startswith("https://remonterletemps.ign.fr/comparer/?")
        for p in points
    )
    assert 'class="f-aerien"' in rapport["html"]
    assert "p.photos_aeriennes" in rendu.SCRIPT and 'rel = "noopener noreferrer"' in rendu.SCRIPT
def test_ensoleillement_v2_dans_la_fiche():
    # 004 T020 : heures juin–août, cause d'ombre et source LiDAR dans la fiche ; version 2.0.
    resultat = copy.deepcopy(_resultat())
    point = resultat.points[0]
    point.facteurs = [f for f in point.facteurs if f.nom != "ensoleillement"]
    point.facteurs.append(
        Facteur(
            "ensoleillement",
            6.5,
            1.02,
            explication="Soleil de juin à août : 6.5 h/jour ; ombre surtout due : arbres "
            "(LiDAR HD de mars 2023)",
            unite="h/jour",
            details={
                "cause_ombre": "arbre",
                "source": "lidar_hd",
                "millesime_lidar": "22LHDKE 2023-03-03",
            },
        )
    )
    html = rendu.rendre(resultat, JournalGeneration("92026", "2.0"))["rapport.html"][0].decode()
    analyse = _Ressources()
    analyse.feed(html)
    donnees = json.loads(next(t for a, t in analyse.scripts if a.get("id") == "donnees"))
    soleil = next(f for f in donnees["points"][0]["facteurs"] if f["nom"] == "ensoleillement")
    assert soleil["details"]["cause_ombre"] == "arbre"
    assert "LiDAR HD de mars 2023" in soleil["explication"]
    assert "Méthode 2.0" in html
