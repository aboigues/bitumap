"""Échantillon pour la vérification manuelle du type de route (T068, SC-005)."""

from tools.echantillon_voirie import COLONNES, echantillon, ligne


def _points(n):
    return [
        {
            "id": f"A{i}",
            "nom": f"Arrêt {i}",
            "voie": "Rue",
            "lon": 2.25,
            "lat": 48.9,
            "route": {"classement": "communale", "gestionnaire": None, "statut": "concordant"},
        }
        for i in range(n)
    ]


def test_tirage_reproductible_et_independant_de_l_ordre():
    points = _points(200)
    premier = [p["id"] for p in echantillon(points)]
    second = [p["id"] for p in echantillon(list(reversed(points)))]
    assert premier == second and len(set(premier)) == 50


def test_moins_de_points_que_la_taille():
    assert len(echantillon(_points(12))) == 12


def test_ligne_a_completer():
    rangee = ligne(_points(1)[0])
    assert list(rangee) == COLONNES
    assert rangee["exact"] == "" and rangee["gestionnaire"] == ""
    assert rangee["lien_geoportail"].startswith(
        "https://www.geoportail.gouv.fr/carte?c=2.250000,48.9"
    )
