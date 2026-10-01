"""Comparaison 1.2 / 2.0 (004 T035, R6) : niveau v1 et raison principale du changement."""

from __future__ import annotations

from pathlib import Path

from bitumap.modele import Facteur, Point
from bitumap.score import combinaison
from bitumap.score.comparaison import (
    RAISON_AUTRES_POINTS,
    Memoire,
    calculer_avec_v1,
    comparer,
    libelle_changement,
    raison,
    reprise_ia,
)
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"


def _point(ident: str, groupe: str, **effets: float) -> Point:
    p = Point(ident, "arret", ident, 2.25, 48.9, groupe=groupe)
    p.facteurs = [Facteur(nom, None, effet) for nom, effet in effets.items()]
    return p


def test_raison_facteur_qui_a_le_plus_varie():
    v1 = _point("A1", "P2", charge=5.0, ensoleillement=1.1, chaleur=1.0)
    v2 = _point("A1", "P1b", charge=5.0, ensoleillement=0.85, poids_lourds=1.2)
    # |ln 0,85 − ln 1,1| = 0,258 > ln 1,2 = 0,182
    assert raison(v1, v2) == "ensoleillement (×1,10 en v1, ×0,85 en v2)"


def test_chaleur_2_0_regroupee_face_a_l_alea():
    v1 = _point("A1", "P1a", charge=5.0, chaleur=0.92)
    v2 = _point(
        "A1",
        "P1b",
        charge=5.0,
        chaleur_alea=1.0,
        chaleur_temperature_surface=1.0,
        chaleur_mineralisation=1.0,
    )
    assert raison(v1, v2) == "chaleur (×0,92 en v1, ×1,00 en v2)"


def test_aucun_facteur_change_classement_relatif():
    v1 = _point("A1", "P2", charge=5.0, ensoleillement=1.0)
    v2 = _point("A1", "P1c", charge=5.0, ensoleillement=1.001)
    assert raison(v1, v2) == RAISON_AUTRES_POINTS


def test_niveau_inchange_raison_nulle_et_bilan():
    v1 = [_point("A1", "P1a", charge=5.0), _point("A2", "P2", charge=3.0)]
    v2 = [_point("A1", "P1a", charge=5.0), _point("A2", "P1a", charge=3.0, poids_lourds=1.25)]
    bilan = comparer(v1, v2)
    assert (v2[0].niveau_v1, v2[0].raison_changement) == ("P1a", None)
    assert v2[1].niveau_v1 == "P2" and v2[1].raison_changement.startswith("poids lourds")
    assert bilan["P1a"]["P1a"] == 1 and bilan["P2"]["P1a"] == 1
    assert sum(n for ligne in bilan.values() for n in ligne.values()) == 2
    assert libelle_changement(v2[0]) is None
    assert libelle_changement(v2[1]) == (
        "v1 : À surveiller — raison : poids lourds (×1,00 en v1, ×1,25 en v2)"
    )


def test_reprise_de_l_ia_sans_appel():
    age = Facteur(combinaison.FACTEUR_IA, "5-12", 0.85, provenance="ia", statut="a_confirmer")
    v2 = [_point("A1", "P1a")]
    v2[0].facteurs.append(age)
    p1_v1 = [_point("A1", "P1a"), _point("A9", "P1b")]
    reprise_ia(v2)(p1_v1)
    assert p1_v1[0].facteur(combinaison.FACTEUR_IA).effet == 0.85
    nouveau = p1_v1[1].facteur(combinaison.FACTEUR_IA)
    assert (nouveau.effet, nouveau.statut) == (1.0, "non_evalue")


class _Compteur:
    def __init__(self):
        self.appels = 0

    def lire(self, x):
        self.appels += 1
        return [x]


def test_memoire_lit_une_fois_et_rend_une_copie():
    source = _Compteur()
    m = Memoire(source)
    premiere = m.lire(1)
    premiere.append("modifié")
    assert m.lire(1) == [1] and source.appels == 1
    m.lire(2)
    assert source.appels == 2


def test_courbevoie_sans_appel_d_ia_supplementaire():
    appels: list[list[str]] = []

    def analyse_ia(points):
        appels.append([p.id for p in points])
        for p in points:
            p.facteurs.append(Facteur(combinaison.FACTEUR_IA, None, 1.0, statut="non_evalue"))

    from bitumap.config import reglages

    ancienne = reglages().methode
    reglages().methode = "2.0"
    try:
        resultat = calculer_avec_v1(FournisseurFige(FIXTURES, "92026"), "Courbevoie", analyse_ia)
    finally:
        reglages().methode = ancienne
    assert len(appels) == 1  # l'IA de la 2.0 seulement
    assert all(p.niveau_v1 for p in resultat.points)
    changes = [p for p in resultat.points if p.niveau_v1 != p.groupe]
    assert changes and all(p.raison_changement for p in changes)
    assert sum(n for ligne in resultat.bilan_changements.values() for n in ligne.values()) == len(
        resultat.points
    )
