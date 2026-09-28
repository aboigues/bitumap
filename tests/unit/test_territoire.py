"""Code postal → communes (FR-001 à FR-003), réponses de l'API Géo figées avec respx."""

import httpx
import pytest
import respx

from bitumap.territoire import ErreurTerritoire, communes_du_code_postal, valider_format
from bitumap.territoire.api_geo import URL_API_GEO


def _repondre(route, donnees):
    route.mock(return_value=httpx.Response(200, json=donnees))


@respx.mock
def test_92400_courbevoie():
    _repondre(
        respx.get(f"{URL_API_GEO}/communes"),
        [{"nom": "Courbevoie", "code": "92026", "codeDepartement": "92"}],
    )
    communes = communes_du_code_postal("92400")
    assert [c.insee for c in communes] == ["92026"]


@respx.mock
def test_95000_quatre_communes():
    _repondre(
        respx.get(f"{URL_API_GEO}/communes"),
        [
            {"nom": "Pontoise", "code": "95500", "codeDepartement": "95"},
            {"nom": "Cergy", "code": "95127", "codeDepartement": "95"},
            {"nom": "Boisemont", "code": "95074", "codeDepartement": "95"},
            {"nom": "Neuville-sur-Oise", "code": "95450", "codeDepartement": "95"},
        ],
    )
    noms = [c.nom for c in communes_du_code_postal("95000")]
    assert noms == ["Boisemont", "Cergy", "Neuville-sur-Oise", "Pontoise"]


@respx.mock
def test_paris_par_arrondissement():
    route = respx.get(f"{URL_API_GEO}/communes")
    _repondre(
        route, [{"nom": "Paris 11e Arrondissement", "code": "75111", "codeDepartement": "75"}]
    )
    communes = communes_du_code_postal("75011")
    assert communes[0].insee == "75111"
    assert route.calls.last.request.url.params["type"] == "arrondissement-municipal"


@pytest.mark.parametrize(
    ("saisie", "code"),
    [
        ("9240", "format_invalide"),
        ("92 400", "format_invalide"),
        ("abcde", "format_invalide"),
        ("69001", "hors_ile_de_france"),
        ("13001", "hors_ile_de_france"),
    ],
)
def test_refus_sans_appel_externe(saisie, code):
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ErreurTerritoire) as erreur:
            valider_format(saisie)
        assert erreur.value.code == code
        assert mock.calls.call_count == 0


@respx.mock
def test_code_inexistant():
    _repondre(respx.get(f"{URL_API_GEO}/communes"), [])
    with pytest.raises(ErreurTerritoire) as erreur:
        communes_du_code_postal("91999")
    assert erreur.value.code == "code_inexistant"
