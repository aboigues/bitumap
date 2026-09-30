"""CSP d'un rapport servi (003 R2, T006) : elle autorise le script en ligne **du document
servi**, pas seulement celui de la version en cours du code. Un rapport encore en cache,
produit avant une modification du script, doit rester interactif."""

import base64
import hashlib

from bitumap import stockage
from bitumap.config import reglages
from bitumap.rapport import rendu
from tests.conftest import connecter

EMPREINTE = "0123456789abcdef"


def _servir(client, courriels, html: str):
    stockage.ecrire(
        reglages().bucket_rapports,
        stockage.prefixe_rapport("92026", EMPREINTE) + "rapport.html",
        html.encode(),
        "text/html; charset=utf-8",
    )
    connecter(client, courriels)
    return client.get(f"/rapports/92026/{EMPREINTE}")


def _empreinte(script: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"


def test_ancien_script_autorise(client, courriels, s3):
    ancien = "document.title = 'rapport produit avec une version antérieure';"
    reponse = _servir(client, courriels, f"<html><body><script>{ancien}</script></body></html>")
    csp = reponse.headers["content-security-policy"]
    assert _empreinte(ancien) in csp
    assert rendu.EMPREINTE_SCRIPT not in csp  # seul le script réellement servi est autorisé


def test_les_donnees_json_ne_sont_pas_des_scripts(client, courriels, s3):
    html = (
        '<html><body><script type="application/json" id="donnees">{"a": 1}</script>'
        "<SCRIPT>var x = 1;</SCRIPT></body></html>"
    )
    csp = _servir(client, courriels, html).headers["content-security-policy"]
    assert _empreinte("var x = 1;") in csp
    assert _empreinte('{"a": 1}') not in csp


def test_document_sans_script(client, courriels, s3):
    csp = _servir(client, courriels, "<html><body><p>rien</p></body></html>").headers[
        "content-security-policy"
    ]
    assert "script-src 'none'" in csp
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
