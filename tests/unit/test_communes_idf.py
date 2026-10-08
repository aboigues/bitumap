"""Liste intégrée des communes et recherche par nom (008 : FR-001 à FR-004, FR-016, SC-001)."""

from __future__ import annotations

import json
from importlib import resources

from bitumap.territoire import recherche
from bitumap.territoire.api_geo import DEPARTEMENTS_IDF


def _fichier() -> dict:
    return json.loads(
        resources.files("bitumap.territoire").joinpath("communes_idf.json").read_text()
    )


def _noms(q: str) -> list[str]:
    return [c.nom for c in recherche.rechercher(q)]


def test_invariants_de_la_liste():
    donnees = _fichier()
    assert {"source", "url", "genere_le"} <= donnees.keys()
    codes = [c[0] for c in donnees["communes"]]
    assert len(codes) >= 1200
    assert len(set(codes)) == len(codes)
    assert all(len(code) == 5 for code in codes)
    assert "75056" not in codes
    assert sum(code.startswith("751") for code in codes) == 20
    assert {c[2] for c in donnees["communes"]} <= DEPARTEMENTS_IDF


def test_normalisation():
    assert recherche.normaliser("Asnières-sur-Seine") == "asnieres sur seine"
    assert recherche.normaliser("L'Haÿ-les-Roses") == "l hay les roses"
    assert recherche.normaliser("  St-Denis ") == "saint denis"
    assert recherche.normaliser("Ste  Geneviève") == "sainte genevieve"
    assert recherche.normaliser("Ville-d’Avray") == "ville d avray"


def test_recherche_par_debut_de_nom():
    assert "Courbevoie" in _noms("courbe")
    assert "Asnières-sur-Seine" in _noms("asnieres")
    assert "Saint-Denis" in _noms("st denis")
    assert "L'Haÿ-les-Roses" in _noms("lhay")


def test_classement_debut_puis_mot_puis_contenu():
    resultats = recherche.rechercher("marne")
    formes = [recherche.normaliser(c.nom) for c in resultats]
    rangs = [0 if f.startswith("marne") else 1 if " marne" in f else 2 for f in formes]
    assert rangs == sorted(rangs)
    assert len(resultats) == 10


def test_arrondissements_de_paris():
    assert "Paris 17e Arrondissement" in _noms("paris 17")
    assert "Paris 17e Arrondissement" in _noms("paris 17e")
    assert _noms("17e")[0] == "Paris 17e Arrondissement"
    assert _noms("1er")[0] == "Paris 1er Arrondissement"
    paris = recherche.rechercher("paris", limite=20)
    assert len(paris) == 20 and all(c.insee.startswith("751") for c in paris)


def test_homonymes_distingues_par_le_departement():
    blandy = [c for c in recherche.rechercher("blandy") if c.nom == "Blandy"]
    assert len({c.departement for c in blandy}) == 2


def test_seuil_de_trois_lettres():
    assert _noms("cou")
    assert _noms("co") == []
    assert _noms("bu") == []
    assert [(c.nom, c.departement) for c in recherche.rechercher("us")] == [("Us", "95")]
    assert _noms("") == []


def test_au_plus_dix_et_saisie_bornee():
    assert len(recherche.rechercher("saint")) == 10
    assert recherche.rechercher("a" * 1000) == []


def test_par_insee():
    assert recherche.par_insee("92026").nom == "Courbevoie"
    assert recherche.par_insee("75056") is None
    assert recherche.par_insee("69123") is None


def test_sc_001_chaque_commune_trouvee():
    communes = _fichier()["communes"]
    manquantes = [nom for insee, nom, _ in communes if insee not in _codes(nom)]
    assert manquantes == []
    lettres = sorted(_lettres_necessaires(insee, nom) for insee, nom, _ in communes)
    mediane = lettres[len(lettres) // 2]
    en_sept = sum(n <= 7 for n in lettres) / len(lettres)
    print(f"SC-001 : médiane {mediane} lettres, {en_sept:.1%} en 7 au plus, max {lettres[-1]}")
    assert mediane <= 3
    assert en_sept >= 0.99
    assert lettres[-1] <= 10


def _lettres_necessaires(insee: str, nom: str) -> int:
    return next(k for k in range(1, len(nom) + 1) if insee in _codes(nom[:k]))


def _codes(q: str) -> set[str]:
    return {c.insee for c in recherche.rechercher(q)}
