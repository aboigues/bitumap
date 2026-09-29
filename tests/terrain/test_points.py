"""Points du rapport en vigueur (003, T009)."""

from bitumap.terrain.points import points_en_vigueur
from tests.conftest import rapport_courbevoie


def test_points_du_rapport_en_vigueur(base, s3):
    empreinte = rapport_courbevoie()
    trouvee, points = points_en_vigueur("92026")
    assert trouvee == empreinte and len(points) == 154
    p = points["A23742"]
    assert p.nom == "Paix - Verdun" and p.groupe.startswith("P") and p.rang > 0
    assert p.designation.startswith("Paix - Verdun · vers")


def test_commune_sans_rapport(base, s3):
    assert points_en_vigueur("92004") == (None, {})
