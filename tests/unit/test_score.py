"""Combinaison, rangs et priorités (FR-011, FR-012, FR-014, SC-012)."""

from bitumap.modele import Facteur, Point
from bitumap.score import combinaison


def _points(n):
    return [
        Point(
            id=f"A{i:03d}",
            type="arret",
            nom=str(i),
            lon=2.27,
            lat=48.9,
            facteurs=[Facteur("charge", i, 1.0 + i / 100)],
        )
        for i in range(n)
    ]


def test_priorites_20_40_40():
    points = combinaison.prioriser(_points(10))
    assert [p.priorite for p in points].count("P1") == 2
    assert [p.priorite for p in points].count("P2") == 4
    assert [p.priorite for p in points].count("P3") == 4


def test_ordre_deterministe_a_egalite():
    points = [
        Point(id=i, type="arret", nom=i, lon=0, lat=0, facteurs=[Facteur("charge", 1, 2.0)])
        for i in ("B", "A", "C")
    ]
    assert [p.id for p in combinaison.prioriser(points)] == ["A", "B", "C"]


def test_ia_ne_change_jamais_la_priorite():
    points = combinaison.prioriser(_points(10))
    p1 = [p for p in points if p.priorite == "P1"]
    # L'IA pénalise fortement le meilleur P1 : il reste P1 mais passe derrière l'autre P1.
    p1[0].facteurs.append(Facteur(combinaison.FACTEUR_IA, "5–8 ans", 0.85, provenance="ia"))
    final = combinaison.finaliser(points)
    assert [p.priorite for p in final].count("P1") == 2
    assert final[0].id == p1[1].id and final[1].id == p1[0].id
    assert final[1].priorite == "P1"


def test_score_affiche_0_100():
    final = combinaison.finaliser(combinaison.prioriser(_points(5)))
    assert final[0].score == 100
    assert all(0 <= p.score <= 100 for p in final)
    assert [p.rang for p in final] == [1, 2, 3, 4, 5]


def test_sous_groupes_du_p1_par_tiers():
    # 154 points (Courbevoie) : 31 P1 ⇒ 11 P1a, 10 P1b, 10 P1c ; P2 et P3 inchangés.
    points = combinaison.finaliser(combinaison.prioriser(_points(154)))
    groupes = [p.groupe for p in points]
    assert (groupes.count("P1a"), groupes.count("P1b"), groupes.count("P1c")) == (11, 10, 10)
    assert groupes.count("P2") == 62 and groupes.count("P3") == 61
    assert groupes == sorted(groupes, key=["P1a", "P1b", "P1c", "P2", "P3"].index)
    assert all(p.priorite == "P1" for p in points if p.groupe.startswith("P1"))


def test_sous_groupes_apres_l_age_de_l_enrobe():
    points = combinaison.prioriser(_points(15))  # 3 P1 : un par tiers
    premier = next(p for p in points if p.priorite == "P1")
    premier.facteurs.append(Facteur(combinaison.FACTEUR_IA, "5–8 ans", 0.5, provenance="ia"))
    points = combinaison.finaliser(points)
    assert premier.priorite == "P1" and premier.groupe == "P1c"  # réordonné dans le P1


def test_petites_communes():
    for n, attendu in ((1, ["P1a"]), (5, ["P1a"]), (10, ["P1a", "P1b"])):
        points = combinaison.finaliser(combinaison.prioriser(_points(n)))
        assert [p.groupe for p in points if p.priorite == "P1"] == attendu
