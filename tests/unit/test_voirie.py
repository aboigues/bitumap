"""Type de route et gestionnaire (FR-013, T063) : BD TOPO recoupée avec la référence OSM."""

import math

from bitumap.facteurs import voirie


def test_boulevard_georges_clemenceau_concordant():
    # Valeurs relevées dans BDTOPO_V3:troncon_de_route (research R6).
    route = voirie.determiner("Départementale", "Hauts-de-Seine", "D9B", "D 9b", "Courbevoie")
    assert route.classement == "départementale"
    assert route.gestionnaire == "Hauts-de-Seine"
    assert route.numero == "D9B"
    assert route.statut == "concordant"


def test_classement_bdtopo_vide_communale_presumee():
    route = voirie.determiner("", None, None, None, "Courbevoie")
    assert route.classement == "communale_presumee"
    assert route.gestionnaire == "Courbevoie"  # la commune, faute de gestionnaire IGN
    assert route.statut == "a_verifier"


def test_valeurs_manquantes_des_tableaux_pandas():
    route = voirie.determiner(math.nan, math.nan, math.nan, math.nan, "Courbevoie")
    assert route.classement == "communale_presumee"


def test_reference_osm_divergente_a_verifier():
    route = voirie.determiner("Départementale", "Hauts-de-Seine", "D9B", "N 13", "Courbevoie")
    assert route.classement == "départementale"  # l'IGN fait foi
    assert route.statut == "a_verifier"


def test_osm_seul_non_confirme():
    route = voirie.determiner(None, None, None, "D 908", "Courbevoie")
    assert route.classement == "départementale"
    assert route.numero == "D908"
    assert route.statut == "a_verifier"
    assert route.gestionnaire is None  # non devinée pour une départementale


def test_aucune_donnee_indetermine():
    route = voirie.determiner(None, None, None, None, "Courbevoie", troncon_trouve=False)
    assert route.classement == "indetermine"
    assert route.statut == "indetermine"
    assert route.gestionnaire is None and route.numero is None


def test_libelles():
    assert voirie.libelle("communale_presumee") == "communale (présumée)"
    assert voirie.libelle("indetermine") == "indéterminé"
