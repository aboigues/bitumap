"""Menu inséré dans le rapport servi (008 US2, FR-015, research R6).

Le rapport stocké n'est jamais modifié : le menu est ajouté à chaque service, selon le
compte qui consulte, y compris pour un rapport produit avant cette fonctionnalité (LL-011).
"""

from __future__ import annotations

from bitumap import stockage
from bitumap.config import reglages
from bitumap.rapport.rendu import csp_du_document
from tests.conftest import connecter, connecter_mainteneur, rapport_courbevoie

EMPREINTE = "0123456789abcdef"
ANCIEN = (
    "<!doctype html><html><head><title>Ancien</title></head>"
    '<body class="x"><div class="page"><h1>Rapport ancien</h1></div>'
    "<script>document.title = 'ancien';</script></body></html>"
)


def _cle(empreinte: str) -> str:
    return stockage.prefixe_rapport("92026", empreinte) + "rapport.html"


def _fragment(page: str) -> str:
    debut = page.index('<nav aria-label="Menu principal"')
    return page[page.rindex("<style", 0, debut) : page.index("</nav>", page.index("Fil d'Ariane"))]


def test_menu_juste_apres_body(client, courriels, s3):
    empreinte = rapport_courbevoie()
    connecter(client, courriels)
    page = client.get(f"/rapports/92026/{empreinte}").text
    apres_body = page.split("<body>", 1)[1].lstrip()
    assert apres_body.startswith("<style")
    assert apres_body.index('<nav aria-label="Menu principal"') < apres_body.index('class="page"')


def test_fragment_sans_script_ni_formulaire(client, courriels, s3):
    empreinte = rapport_courbevoie()
    connecter(client, courriels)
    fragment = _fragment(client.get(f"/rapports/92026/{empreinte}").text)
    assert "<script" not in fragment and "<form" not in fragment
    assert "Se déconnecter" not in fragment
    assert "Mes demandes" in fragment and 'aria-current="page"' in fragment


def test_csp_et_ordre_des_blocs_inchanges(client, courriels, s3):
    empreinte = rapport_courbevoie()
    stocke = stockage.lire(reglages().bucket_rapports, _cle(empreinte)).decode()
    connecter(client, courriels)
    reponse = client.get(f"/rapports/92026/{empreinte}")
    assert reponse.headers["content-security-policy"] == csp_du_document(stocke)
    html = reponse.text
    assert html.index('id="donnees"') < html.index('id="releves"') < html.index("<script>")


def test_rapport_d_une_version_anterieure(client, courriels, s3):
    stockage.ecrire(
        reglages().bucket_rapports, _cle(EMPREINTE), ANCIEN.encode(), "text/html; charset=utf-8"
    )
    connecter(client, courriels)
    reponse = client.get(f"/rapports/92026/{EMPREINTE}")
    assert '<nav aria-label="Menu principal"' in reponse.text
    assert reponse.text.index("Menu principal") < reponse.text.index("Rapport ancien")
    assert reponse.headers["content-security-policy"] == csp_du_document(ANCIEN)
    assert "Courbevoie" in _fragment(reponse.text)  # fil : Accueil › Mes demandes › Courbevoie


def test_menu_du_compte_qui_consulte(client, courriels, s3, monkeypatch):
    empreinte = rapport_courbevoie()
    connecter(client, courriels)
    assert "Modération" not in client.get(f"/rapports/92026/{empreinte}").text
    client.cookies.clear()
    connecter_mainteneur(client, courriels, monkeypatch)
    assert "Modération" in _fragment(client.get(f"/rapports/92026/{empreinte}").text)


def test_rapport_stocke_jamais_modifie(client, courriels, s3):
    empreinte = rapport_courbevoie()
    avant = stockage.lire(reglages().bucket_rapports, _cle(empreinte))
    connecter(client, courriels)
    client.get(f"/rapports/92026/{empreinte}")
    assert stockage.lire(reglages().bucket_rapports, _cle(empreinte)) == avant
