"""Menu commun et pages de choix de commune (008 US2, contracts/interface.md)."""

from __future__ import annotations

import html
import re

import pytest

from bitumap.db import connexion
from bitumap.lot import versions
from tests.conftest import connecter, connecter_mainteneur

EMPREINTE = "0123456789abcdef"
TOUTES = ["Accueil", "Mes demandes", "Relevés terrain", "Parcours", "Mon compte", "Modération"]


def _menu(page: str) -> list[str]:
    """Libellés du menu pour écran large (la liste repliable a les mêmes)."""
    bloc = page.split('<nav aria-label="Menu principal"', 1)[1].split("</nav>", 1)[0]
    large = bloc.split('class="large"', 1)[1].split("</ul>", 1)[0]
    return [html.unescape(x) for x in re.findall(r">([^<>]+)</a>", large)]


def _courante(page: str) -> list[str]:
    bloc = page.split('<nav aria-label="Menu principal"', 1)[1].split("</nav>", 1)[0]
    large = bloc.split('class="large"', 1)[1].split("</ul>", 1)[0]
    return re.findall(r'aria-current="page"[^>]*>([^<]+)<', large)


def _terminer(insee: str, nom: str, empreinte: str = EMPREINTE, jours: int = 0) -> None:
    with connexion() as conn:
        conn.execute(
            "INSERT INTO demande (commune_insee, commune_nom, empreinte, etat, termine_le)"
            " VALUES (%s, %s, %s, 'terminee', now() - make_interval(days => %s))",
            (insee, nom, empreinte, jours),
        )


@pytest.fixture
def empreinte_fixe(monkeypatch):
    monkeypatch.setattr(versions, "empreinte_courante", lambda insee: EMPREINTE)


def test_menu_du_visiteur(client):
    for chemin in ("/", "/confidentialite", "/page-inexistante"):
        page = client.get(chemin).text
        assert _menu(page) == ["Accueil", "Données personnelles"], chemin
        for reservee in ("/demandes", "/terrain", "/parcours", "/compte"):
            assert f'href="{reservee}"' not in page, (chemin, reservee)


def test_menu_d_un_agent(client, courriels):
    connecter(client, courriels)
    page = client.get("/").text
    assert _menu(page) == TOUTES[:-1]
    assert "/terrain/moderation" not in page and "Modération" not in page


def test_menu_du_mainteneur(client, courriels, monkeypatch):
    connecter_mainteneur(client, courriels, monkeypatch)
    assert _menu(client.get("/").text) == TOUTES


@pytest.mark.parametrize(
    ("chemin", "courante"),
    [
        ("/", "Accueil"),
        ("/communes?q=courbe", "Accueil"),
        ("/demandes", "Mes demandes"),
        ("/compte", "Mon compte"),
        ("/terrain", "Relevés terrain"),
        ("/parcours", "Parcours"),
    ],
)
def test_entree_courante(client, courriels, chemin, courante):
    connecter(client, courriels)
    assert _courante(client.get(chemin).text) == [courante]


def test_menu_repliable_sans_script(client, courriels):
    connecter(client, courriels)
    page = client.get("/demandes").text
    assert "<details><summary>Menu</summary>" in page
    assert "<script" not in page.split('<nav aria-label="Menu principal"', 1)[1].split("</nav>")[0]


def test_page_d_erreur_avec_le_menu_du_compte(client, courriels):
    connecter(client, courriels)
    reponse = client.get("/page-inexistante")
    assert reponse.status_code == 404
    assert _menu(reponse.text) == TOUTES[:-1]


@pytest.mark.parametrize(("rubrique", "titre"), [("terrain", "Relevés"), ("parcours", "Parcours")])
def test_choix_parmi_les_rapports_disponibles(client, courriels, empreinte_fixe, rubrique, titre):
    _terminer("92026", "Courbevoie")
    _terminer("92004", "Asnières-sur-Seine", empreinte="fedcba9876543210")  # périmée
    _terminer("92025", "Colombes", jours=60)  # au-delà de cache_rapport_jours
    connecter(client, courriels, "autre@exemple.fr")
    page = client.get(f"/{rubrique}").text
    assert titre in page
    assert f'href="/{rubrique}/92026"' in page
    assert "Asnières" not in page and "Colombes" not in page
    assert "agent@" not in page and "autre@" not in page.split("<main", 1)[1]


def test_commune_sans_rapport_propose_la_demande(client, courriels, empreinte_fixe):
    connecter(client, courriels)
    page = client.get("/terrain", params={"q": "asnieres"}).text
    assert 'href="/communes?insee=92004"' in page and "Demander le rapport" in page
    assert 'href="/terrain/92004"' not in page


def test_commune_avec_rapport_trouvee_par_la_recherche(client, courriels, empreinte_fixe):
    _terminer("92026", "Courbevoie")
    connecter(client, courriels)
    page = client.get("/parcours", params={"q": "courbe"}).text
    assert 'href="/parcours/92026"' in page


def test_choix_par_insee(client, courriels, empreinte_fixe):
    _terminer("92026", "Courbevoie")
    connecter(client, courriels)
    reponse = client.get("/terrain", params={"insee": "92026"}, follow_redirects=False)
    assert reponse.status_code == 303 and reponse.headers["location"] == "/terrain/92026"
    page = client.get("/parcours", params={"insee": "92004"}).text
    assert 'href="/communes?insee=92004"' in page


def test_pages_de_choix_sans_session(client):
    for rubrique in ("terrain", "parcours"):
        reponse = client.get(f"/{rubrique}", follow_redirects=False)
        assert reponse.status_code == 303
        assert reponse.headers["location"] == f"/?motif=session&suite=%2F{rubrique}"


def test_pages_existantes_inchangees(client, courriels, monkeypatch):
    connecter_mainteneur(client, courriels, monkeypatch)
    assert client.get("/terrain/moderation").status_code == 200


# --- Fil d'Ariane (008 US3) -------------------------------------------------------------


def _fil(page: str) -> list[tuple[str, str | None]]:
    if 'aria-label="Fil d\'Ariane"' not in page:
        return []
    bloc = page.split('aria-label="Fil d\'Ariane"', 1)[1].split("</nav>", 1)[0]
    elements = []
    for li in re.findall(r"<li>(.*?)</li>", bloc, re.S):
        lien = re.search(r'<a href="([^"]+)">([^<]+)</a>', li)
        if lien:
            elements.append((html.unescape(lien.group(2)), lien.group(1)))
        else:
            courant = re.search(r'<span aria-current="page">([^<]+)</span>', li)
            elements.append((html.unescape(courant.group(1)), None))
    return elements


@pytest.mark.parametrize(
    ("chemin", "attendu"),
    [
        ("/communes?q=courbe", [("Choisir la commune", None)]),
        ("/demandes", [("Mes demandes", None)]),
        ("/compte", [("Mon compte", None)]),
        ("/confidentialite", [("Données personnelles", None)]),
        ("/terrain", [("Relevés terrain", None)]),
        ("/parcours", [("Parcours", None)]),
        ("/page-inexistante", [("Erreur", None)]),
    ],
)
def test_fil_des_pages_simples(client, courriels, chemin, attendu):
    connecter(client, courriels)
    assert _fil(client.get(chemin).text) == [("Accueil", "/"), *attendu]


def test_accueil_sans_fil(client, courriels):
    connecter(client, courriels)
    assert _fil(client.get("/").text) == []


def test_fil_de_la_moderation(client, courriels, monkeypatch):
    connecter_mainteneur(client, courriels, monkeypatch)
    assert _fil(client.get("/terrain/moderation").text) == [("Accueil", "/"), ("Modération", None)]


def test_fil_des_pages_de_terrain(client, courriels, s3):
    from tests.conftest import rapport_courbevoie

    rapport_courbevoie()
    connecter(client, courriels)
    assert _fil(client.get("/terrain/92026").text) == [
        ("Accueil", "/"),
        ("Relevés terrain", "/terrain"),
        ("Courbevoie", None),
    ]
    assert _fil(client.get("/terrain/92026/A27418").text) == [
        ("Accueil", "/"),
        ("Relevés terrain", "/terrain"),
        ("Courbevoie", "/terrain/92026"),
        ("Point A27418", None),
    ]
    assert _fil(client.get("/parcours/92026").text) == [
        ("Accueil", "/"),
        ("Parcours", "/parcours"),
        ("Courbevoie", None),
    ]


def test_fil_du_suivi(client, courriels, territoire, s3):
    from tests.conftest import preuve

    csrf = connecter(client, courriels)
    reponse = client.post(
        "/demandes",
        data={"insee": "92026", "csrf": csrf, "altcha": preuve(client)},
        follow_redirects=False,
    )
    assert _fil(client.get(reponse.headers["location"]).text) == [
        ("Accueil", "/"),
        ("Mes demandes", "/demandes"),
        ("Courbevoie", None),
    ]


def test_fil_echappe(client, courriels):
    connecter(client, courriels)
    page = client.get("/communes", params={"q": "<b>x</b>"}).text
    assert "<b>x</b>" not in page
