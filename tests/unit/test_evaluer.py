"""Évaluation comparative des modèles vision (T072, SC-012), sans réseau."""

import json

from bitumap.ia import evaluer
from bitumap.ia.client import Appel, ReponseAge
from tests.lot.aides import IMAGES

ECHANTILLON = [
    {"id": "A1", "nom": "Un", "lon": 2.25, "lat": 48.9, "refection_annee": 2016, "source": "t"},
    {"id": "A2", "nom": "Deux", "lon": 2.26, "lat": 48.9, "refection_annee": 2022, "source": "t"},
    {"id": "A3", "nom": "Trois", "lon": 2.27, "lat": 48.9, "refection_annee": 2008, "source": "t"},
]
# Réponses simulées par modèle et par point : (début, fin, statut) ou None (hors schéma)
REPONSES = {
    "exact-cher": {"A1": (2015, 2017), "A2": (2021, 2023), "A3": (2007, 2010)},
    "exact-econome": {"A1": (2016, 2018), "A2": (2022, 2022), "A3": (2008, 2008)},
    "approximatif": {"A1": (2018, 2019), "A2": None, "A3": "indetermine"},
}
JETONS = {"exact-cher": (3000, 200), "exact-econome": (1500, 80), "approximatif": (1000, 50)}


def _appel(prompt, vignettes, modele):
    point = _appel.courant
    valeur = REPONSES[modele][point]
    jetons = JETONS[modele]
    if valeur is None:
        return Appel(None, "pas du JSON", *jetons)
    if valeur == "indetermine":
        reponse = ReponseAge(statut="indetermine", confiance=0.2, justification="flou")
    else:
        reponse = ReponseAge(
            derniere_refection_debut=valeur[0],
            derniere_refection_fin=valeur[1],
            statut="visible",
            confiance=0.8,
            justification="réfection visible",
        )
    return Appel(reponse, reponse.model_dump_json(), *jetons)


def _vignettes(lon, lat):
    _appel.courant = next(p["id"] for p in ECHANTILLON if p["lon"] == lon)
    return IMAGES


def _bilans(monkeypatch):
    monkeypatch.setitem(evaluer.TARIFS, "exact-cher", (evaluer.Decimal("2"), evaluer.Decimal("8")))
    monkeypatch.setitem(
        evaluer.TARIFS, "exact-econome", (evaluer.Decimal("0.1"), evaluer.Decimal("0.3"))
    )
    monkeypatch.setitem(
        evaluer.TARIFS, "approximatif", (evaluer.Decimal("0.1"), evaluer.Decimal("0.1"))
    )
    return evaluer.evaluer(
        ECHANTILLON, tuple(REPONSES), vignettes=_vignettes, appel=_appel, annee=2026
    )


def test_exactitude_et_classe_d_effet(monkeypatch):
    bilans = {b.modele: b for b in _bilans(monkeypatch)}
    assert bilans["exact-cher"].taux("bonne_periode") == 1.0
    approx = bilans["approximatif"]
    assert approx.taux("bonne_periode") == 0.0
    assert approx.non_evalues == 2  # hors schéma + indéterminé
    assert approx.mesures[1].erreur == "réponse hors schéma"
    # A1 : 2018–2019 au lieu de 2016 : mauvaise période, mais même classe d'effet (5–12 ans)
    assert approx.mesures[0].bonne_classe and not approx.mesures[0].bonne_periode


def test_cout_reel_selon_le_tarif(monkeypatch):
    bilans = {b.modele: b for b in _bilans(monkeypatch)}
    # 3 appels × (3000 × 2 € + 200 × 8 €) / 1 M
    assert bilans["exact-cher"].cout_eur == evaluer.Decimal("0.0228")


def test_retenu_le_plus_exact_puis_le_moins_cher(monkeypatch):
    bilans = _bilans(monkeypatch)
    assert evaluer.retenu(bilans).modele == "exact-econome"


def test_rapport_markdown(monkeypatch):
    texte = evaluer.rapport_markdown(_bilans(monkeypatch))
    assert "`exact-econome`" in texte and "SC-012 atteint (100%)" in texte
    assert "| A3 | 2008 |" in texte and "indetermine" in texte
    assert "Aucun changement de priorité dû à l'IA seule" in texte


def test_point_en_erreur_n_arrete_pas_l_evaluation(monkeypatch):
    def vignettes_en_panne(lon, lat):
        raise TimeoutError

    bilan = evaluer.evaluer(ECHANTILLON[:2], ("exact-cher",), vignettes_en_panne, _appel, 2026)[0]
    assert [m.erreur for m in bilan.mesures] == ["TimeoutError", "TimeoutError"]


def test_ligne_de_commande(tmp_path, monkeypatch):
    fichier = tmp_path / "echantillon.json"
    fichier.write_text(json.dumps({"points": ECHANTILLON}), encoding="utf-8")
    sortie = tmp_path / "evaluation.md"
    monkeypatch.setattr(
        evaluer,
        "evaluer",
        lambda points, modeles: [evaluer.Bilan(m, []) for m in modeles],
    )
    assert evaluer.main(["--echantillon", str(fichier), "--sortie", str(sortie)]) == 0
    assert "mistral-small-3.2-24b-instruct-2506" in sortie.read_text(encoding="utf-8")
