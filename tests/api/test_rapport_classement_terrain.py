"""Classement corrigé par le terrain dans le rapport servi (004 T047, R9) : bloc inséré à la
consultation d'un rapport 2.0, après « releves » et avant le script (LL-012) ; rapport stocké
inchangé (principe VI) ; CSP inchangée (bloc JSON exclu, LL-011)."""

from __future__ import annotations

import pytest

from bitumap import stockage
from bitumap.config import reglages
from bitumap.rapport.rendu import csp_du_document
from tests.api.test_rapport_releves import _blocs
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain.aides import deposer

HEROLD = "A36862"  # « Hérold - Mairie de Courbevoie », réaménagé en 2018–2021
_FICHIERS_V2: dict = {}


def _rapport_v2(monkeypatch) -> str:
    """Rapport 2.0 figé de Courbevoie, en vigueur ; renvoie son empreinte."""
    from bitumap.journal import JournalGeneration
    from bitumap.lot import versions
    from bitumap.rapport import rendu
    from bitumap.score.comparaison import calculer_avec_v1
    from tests.lot.aides import fabrique_figee, regional_fige

    monkeypatch.setattr(reglages(), "methode", "2.0")
    monkeypatch.setattr(reglages(), "ete_reference", 2026)
    if not _FICHIERS_V2:
        resultat = calculer_avec_v1(fabrique_figee("92026"), "Courbevoie")
        _FICHIERS_V2.update(rendu.rendre(resultat, JournalGeneration("92026", "2.0")))
    regional_fige(None)
    empreinte = versions.empreinte_courante("92026")
    stockage.ecrire_rapport("92026", empreinte, dict(_FICHIERS_V2))
    return empreinte


def _ordre_des_blocs(html: str) -> list[str]:
    reperes = ('id="donnees"', 'id="releves"', 'id="classement-terrain"', "<script>")
    return sorted(reperes, key=lambda r: html.find(r))


@pytest.fixture
def v2(client, courriels, s3, monkeypatch):
    empreinte = _rapport_v2(monkeypatch)
    csrf = connecter(client, courriels, "agent@exemple.fr")
    return empreinte, csrf


def test_refection_confirmee_fait_descendre_le_point(client, v2):
    empreinte, csrf = v2
    prefixe = stockage.prefixe_rapport("92026", empreinte)
    stockes = {
        n: stockage.lire(reglages().bucket_rapports, prefixe + n)
        for n in ("rapport.html", "points.geojson")
    }
    avant = _blocs(client.get(f"/rapports/92026/{empreinte}").text)
    assert avant["classement-terrain"] == {
        "points": {},
        "nb_points_corriges": 0,
        "classement": avant["classement-terrain"]["classement"],
    }
    rang_estime = next(p["rang"] for p in avant["donnees"]["points"] if p["id"] == HEROLD)

    _, reponse = deposer(
        client,
        csrf,
        point_id=HEROLD,
        niveau="absent",
        annee_refection=2020,
        source_refection="constatee",
    )
    assert reponse.status_code in (200, 201), reponse.text
    html = client.get(f"/rapports/92026/{empreinte}").text
    apres = _blocs(html)
    corrige = apres["classement-terrain"]["points"][HEROLD]
    assert (corrige["effet"], corrige["annee_refection"], corrige["annule"]) == (0.8, 2020, False)
    assert corrige["rang"] > rang_estime
    assert apres["classement-terrain"]["nb_points_corriges"] == 1
    # Estimé inchangé ; rapport stocké inchangé ; blocs dans l'ordre (LL-012).
    assert apres["donnees"] == avant["donnees"]
    for nom, contenu in stockes.items():
        assert stockage.lire(reglages().bucket_rapports, prefixe + nom) == contenu
    assert _ordre_des_blocs(html) == [
        'id="donnees"',
        'id="releves"',
        'id="classement-terrain"',
        "<script>",
    ]
    # Même rapport consulté deux fois : même bloc ; CSP limitée au script du document.
    assert (
        _blocs(client.get(f"/rapports/92026/{empreinte}").text)["classement-terrain"]
        == (apres["classement-terrain"])
    )
    reponse = client.get(f"/rapports/92026/{empreinte}")
    assert reponse.headers["content-security-policy"] == csp_du_document(
        stockes["rapport.html"].decode()
    )


def test_estimee_par_l_agent_et_releve_retire_sans_effet(client, v2):
    empreinte, csrf = v2
    deposer(
        client,
        csrf,
        point_id=HEROLD,
        niveau="absent",
        annee_refection=2020,
        source_refection="estimee_agent",
    )
    bloc = _blocs(client.get(f"/rapports/92026/{empreinte}").text)["classement-terrain"]
    assert bloc["points"] == {}

    releve_id, _ = deposer(
        client,
        csrf,
        point_id=HEROLD,
        niveau="absent",
        annee_refection=2020,
        source_refection="services_techniques",
    )
    bloc = _blocs(client.get(f"/rapports/92026/{empreinte}").text)["classement-terrain"]
    assert bloc["points"][HEROLD]["effet"] == 0.8
    retrait = client.post(
        f"/terrain/releves/{releve_id}/retrait",
        json={"csrf": csrf},
        headers={"accept": "application/json"},
    )
    assert retrait.status_code in (200, 204), retrait.text
    bloc = _blocs(client.get(f"/rapports/92026/{empreinte}").text)["classement-terrain"]
    assert bloc["points"] == {}


def test_ornierage_apres_travaux_annule(client, v2):
    empreinte, csrf = v2
    deposer(
        client,
        csrf,
        point_id=HEROLD,
        niveau="marque",
        annee_refection=2020,
        source_refection="constatee",
    )
    corrige = _blocs(client.get(f"/rapports/92026/{empreinte}").text)["classement-terrain"][
        "points"
    ][HEROLD]
    assert (corrige["effet"], corrige["annule"]) == (1.0, True)
    assert corrige["motif"].startswith("réfection sans effet")


def test_rapport_1_2_sans_bloc(client, courriels, s3):
    empreinte = rapport_courbevoie()
    connecter(client, courriels, "agent@exemple.fr")
    blocs = _blocs(client.get(f"/rapports/92026/{empreinte}").text)
    assert "releves" in blocs and "classement-terrain" not in blocs
