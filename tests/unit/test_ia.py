"""IA vision : bornes, cache, budget, réponses invalides (FR-014, FR-024, SC-007, SC-012)."""

from decimal import Decimal

import pytest
from PIL import Image

from bitumap.config import reglages
from bitumap.ia import age_enrobe, budget
from bitumap.ia.client import Appel, ReponseAge
from bitumap.journal import StatistiquesIA
from bitumap.modele import Point

IMAGES = [(a, Image.new("RGB", (8, 8), (a % 255, 0, 0))) for a in (2003, 2011, 2018, 2024)]


def _p1():
    return Point(id="A1", type="arret", nom="x", lon=2.27, lat=48.9, priorite="P1")


def _reponse(debut, fin, statut="visible"):
    return ReponseAge(
        derniere_refection_debut=debut,
        derniere_refection_fin=fin,
        statut=statut,
        confiance=0.8,
        justification="test",
    )


class Faux:
    def __init__(self, reponse, jetons=(2000, 100), erreur=None):
        self.reponse, self.jetons, self.erreur, self.appels = reponse, jetons, erreur, 0

    def __call__(self, prompt, vignettes):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        brut = self.reponse.model_dump_json() if self.reponse else "pas du json"
        return Appel(self.reponse, brut, *self.jetons)


def _analyser(faux, vignettes=IMAGES):
    stats = StatistiquesIA()
    a = age_enrobe.AnalyseurAge(
        lambda lon, lat: vignettes, budget.BudgetRapport(), stats, faux, annee=2026
    )
    p = _p1()
    a([p])
    return p.facteur("age_enrobe"), stats, a


@pytest.mark.parametrize(
    ("debut", "fin", "effet"), [(2021, 2024, 1.0), (2014, 2017, 0.85), (2003, 2008, 1.05)]
)
def test_effet_borne(base, debut, fin, effet):
    f, _, _ = _analyser(Faux(_reponse(debut, fin)))
    assert f.effet == effet
    assert f.statut == "a_confirmer" and f.provenance == "ia" and f.modele


def test_marquage_sans_effet(base):
    f, _, _ = _analyser(Faux(_reponse(2018, 2021, "marquage")))
    assert f.effet == 1.0 and f.statut == "a_confirmer"


def test_reponse_hors_schema_non_evaluee(base):
    f, stats, _ = _analyser(Faux(None))
    assert f.statut == "non_evalue" and stats.non_evalues == 1


def test_service_en_erreur_non_evalue(base):
    f, _, _ = _analyser(Faux(None, erreur=RuntimeError("panne")))
    assert f.statut == "non_evalue"


def test_cache_evite_un_second_appel(base):
    faux = Faux(_reponse(2014, 2017))
    _analyser(faux)
    f, stats, _ = _analyser(faux)
    assert faux.appels == 1 and stats.succes_cache == 1 and f.effet == 0.85


def test_budget_epuise_aucun_appel(base, monkeypatch):
    monkeypatch.setattr(reglages(), "ia_plafond_rapport_eur", Decimal("0.00001"))
    faux = Faux(_reponse(2014, 2017))
    f, stats, _ = _analyser(faux)
    assert faux.appels == 0 and f.statut == "non_evalue" and stats.cout_eur == 0


def test_plafond_journalier_jamais_depasse(base, monkeypatch):
    monkeypatch.setattr(reglages(), "ia_plafond_jour_eur", Decimal("0.001"))
    b = budget.BudgetRapport()
    reservations = [b.reserver(Decimal("0.0004")) for _ in range(5)]
    assert reservations.count(True) == 2
    assert budget.budget_jour_epuise() is False or budget.cout_du_mois() <= Decimal("0.001")


def test_un_seul_millesime_non_evalue(base):
    f, _, _ = _analyser(Faux(_reponse(2014, 2017)), vignettes=IMAGES[:1])
    assert f.statut == "non_evalue"


def test_reponse_brute_conservee(base):
    _, _, a = _analyser(Faux(_reponse(2014, 2017)))
    assert a.bruts["A1"]["millesimes"] == [2003, 2011, 2018, 2024]


def test_choix_des_millesimes_garde_le_plus_recent():
    vignettes = [(a, None) for a in range(2003, 2025)]
    choisis = [a for a, _ in age_enrobe.choisir_millesimes(vignettes)]
    assert len(choisis) == 6 and choisis[0] == 2003 and choisis[-1] == 2024


def test_alerte_mensuelle_une_seule_fois(base, courriels, monkeypatch):
    monkeypatch.setattr(reglages(), "email_mainteneur", "mainteneur@exemple.fr")
    monkeypatch.setattr(reglages(), "alerte_mensuelle_eur", Decimal("0.001"))
    b = budget.BudgetRapport()
    b.reserver(Decimal("0.002"))
    b.ajuster(Decimal("0.002"), Decimal("0.002"))
    b.ajuster(Decimal("0"), Decimal("0"))
    alertes = [c for c in courriels if "coût IA du mois" in c.sujet]
    assert len(alertes) == 1
