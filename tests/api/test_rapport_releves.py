"""Constaté dans le rapport servi (003 US2, T022) : bloc de données inséré à la consultation,
rapport stocké inchangé, score inchangé (SC-004), aucune photo exposée (FR-015)."""

import json
from html.parser import HTMLParser

from bitumap import stockage
from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import connecter, rapport_courbevoie
from tests.terrain import images
from tests.terrain.aides import POINT, deposer, envoyer_photo


class _Blocs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocs: dict[str, str] = {}
        self._id = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._id = a.get("id") if tag == "script" and a.get("type") == "application/json" else None

    def handle_data(self, data):
        if self._id:
            self.blocs[self._id] = self.blocs.get(self._id, "") + data

    def handle_endtag(self, tag):
        self._id = None


def _blocs(html: str) -> dict:
    analyse = _Blocs()
    analyse.feed(html)
    return {k: json.loads(v) for k, v in analyse.blocs.items()}


def _points(donnees: dict) -> dict:
    return {p["id"]: (p["score"], p["rang"], p["groupe"]) for p in donnees["points"]}


def test_constate_insere_et_score_inchange(client, courriels, s3):
    empreinte = rapport_courbevoie()
    cle = stockage.prefixe_rapport("92026", empreinte) + "rapport.html"
    stocke_avant = stockage.lire(reglages().bucket_rapports, cle)
    csrf = connecter(client, courriels, "a@exemple.fr")
    avant = _blocs(client.get(f"/rapports/92026/{empreinte}").text)
    assert avant["releves"] == {}

    releve_id, _ = deposer(
        client,
        csrf,
        niveau="marque",
        profondeur_mm=18,
        instrument="règle et cale",
        annee_refection=2019,
        source_refection="services_techniques",
        observation="ornière nette",
    )
    envoyer_photo(client, csrf, releve_id, images.png(), "image/png")

    client.cookies.clear()
    connecter(client, courriels, "b@exemple.fr")
    html = client.get(f"/rapports/92026/{empreinte}").text
    apres = _blocs(html)
    constat = apres["releves"][POINT]
    assert constat["niveau"] == "marque" and constat["profondeur_mm"] == 18
    assert constat["annee_refection"] == 2019 and constat["observation"] == "ornière nette"
    assert constat["auteur"].startswith("agent ") and constat["auteur"].endswith("exemple.fr")
    assert constat["nb_photos"] == 1 and constat["nb_releves"] == 1
    # aucun identifiant ni lien de photo pour un autre compte (FR-015)
    with connexion() as conn:
        photo_id = str(conn.execute("SELECT id FROM photo").fetchone()["id"])
    assert photo_id not in html and "/terrain/photos/" not in html
    # score, rang et niveau identiques (SC-004) ; rapport stocké inchangé
    assert _points(apres["donnees"]) == _points(avant["donnees"])
    assert stockage.lire(reglages().bucket_rapports, cle) == stocke_avant


def test_auteur_voit_vous_et_releve_retire_absent(client, courriels, s3):
    empreinte = rapport_courbevoie()
    csrf = connecter(client, courriels)
    releve_id, _ = deposer(client, csrf)
    constat = _blocs(client.get(f"/rapports/92026/{empreinte}").text)["releves"][POINT]
    assert constat["auteur"] == "vous"
    with connexion() as conn:
        conn.execute("UPDATE releve SET retire_le = now() WHERE id = %s", (releve_id,))
    assert _blocs(client.get(f"/rapports/92026/{empreinte}").text)["releves"] == {}


def test_bloc_avant_le_script_qui_le_lit(client, courriels, s3):
    # Le script du rapport lit le bloc au chargement : inséré après lui, il serait ignoré.
    empreinte = rapport_courbevoie()
    connecter(client, courriels)
    html = client.get(f"/rapports/92026/{empreinte}").text
    releves = html.index('id="releves"')
    assert html.index('id="donnees"') < releves < html.index("<script>")


def test_script_du_rapport_toujours_autorise(client, courriels, s3):
    empreinte = rapport_courbevoie()
    connecter(client, courriels)
    reponse = client.get(f"/rapports/92026/{empreinte}")
    assert "script-src 'sha256-" in reponse.headers["content-security-policy"]
    assert "Constaté" in reponse.text  # section prévue par le gabarit du rapport
