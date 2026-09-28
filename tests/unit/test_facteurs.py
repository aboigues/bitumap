"""Facteurs de la méthode 1.0 (effets et bornes)."""

import math

import numpy as np
import pytest

from bitumap.facteurs import chaleur, charge, ensoleillement, site, sollicitation
from bitumap.modele import Point
from bitumap.sources.idfm import agreger


def _point(**kw):
    base = {"id": "A1", "type": "arret", "nom": "x", "lon": 2.27, "lat": 48.9, "bus_jour": 100}
    return Point(**{**base, **kw})


def test_charge_logarithmique():
    assert charge.calculer(_point(bus_jour=100)).effet == pytest.approx(math.log(101))


@pytest.mark.parametrize(("type_", "effet"), [("arret", 1.0), ("feu", 0.8), ("giratoire", 0.7)])
def test_sollicitation_par_type(type_, effet):
    assert sollicitation.calculer(_point(type=type_), None)[0].effet == effet


def test_arret_pres_feu_et_pointe():
    noms = {f.nom: f.effet for f in sollicitation.calculer(_point(pointe_h=21), 35)}
    assert noms["arret_pres_feu"] == 1.2 and noms["pointe"] == 1.1
    noms = {f.nom for f in sollicitation.calculer(_point(pointe_h=19.9), 40)}
    assert noms == {"type"}


@pytest.mark.parametrize(
    ("pente", "effet"), [(0.5, 1.0), (2.9, 1.0), (3.0, 1.08), (5.2, 1.256), (8.0, 1.32)]
)
def test_effet_pente(pente, effet):
    assert site.pente(pente).effet == pytest.approx(effet)


def test_pente_douteuse_ignoree():
    f = site.pente(9.1)
    assert f.effet == 1.0 and f.statut == "non_evalue"


def test_revetement_rigide():
    assert site.revetement("paving_stones", True).effet == 0.5


@pytest.mark.parametrize(("alea", "effet"), [(0, 0.92), (8, 1.0), (16, 1.08)])
def test_effet_chaleur(alea, effet):
    assert chaleur.calculer(alea, "2").effet == pytest.approx(effet)


def test_chaleur_absente_non_evaluee():
    assert chaleur.calculer(None, None).statut == "non_evalue"
    assert chaleur.calculer(-1, None).statut == "non_evalue"


@pytest.mark.parametrize(("heures", "effet"), [(0, 0.8), (6, 1.0), (12, 1.2), (13, 1.2)])
def test_effet_ensoleillement(heures, effet):
    assert ensoleillement.effet_heures(heures) == pytest.approx(effet)


def test_ensoleillement_sans_obstacle_puis_canyon():
    az, el = ensoleillement.positions_soleil(48.9, 2.27)
    degage = np.zeros((200, 200), dtype=np.float32)
    assert ensoleillement.heures_de_soleil(degage, az, el) >= 11.5
    canyon = np.full((200, 200), 60.0, dtype=np.float32)
    canyon[:, 95:105] = 0  # rue nord-sud de 10 m entre des bâtiments de 60 m
    assert ensoleillement.heures_de_soleil(canyon, az, el) <= 2


def test_decaler_masque():
    m = np.zeros((5, 5), bool)
    m[2, 2] = True
    assert ensoleillement.decaler(m, 1, 0)[2, 1]  # point déplacé vers l'est : arbre à l'ouest


def test_offre_idfm_formules_du_prototype():
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    lignes = [
        {
            "libelle_mode_ligne": "Bus",
            "id_arret": "1",
            "nom_arret": "A",
            "latitude_arret": 48.9,
            "longitude_arret": 2.27,
            "nom_ligne_commerciale": "275",
            "tranche_horaire": h,
            **{f"nb_courses_{j}": (7.0 if j not in ("samedi", "dimanche") else 0.0) for j in jours},
        }
        for h in (8, 9)
    ]
    arret = agreger(lignes)["1"]
    assert arret.bus_jour == pytest.approx(2 * 7 * 5 / 7)  # moyenne hebdomadaire
    assert arret.pointe_h == pytest.approx(7.0)  # maximum horaire d'un jour de semaine
