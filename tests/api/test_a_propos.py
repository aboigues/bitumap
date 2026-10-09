"""Page « À propos » et mentions légales (issue #57). L'identité de l'éditeur vient de la
configuration, jamais du dépôt : valeurs fictives ici."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bitumap.config import Reglages, reglages

EDITEUR = {
    "nom": "Exemple Formation",
    "forme": "EI",
    "responsable": "Camille Exemple",
    "siret": "000 000 000 00000",
    "adresse": "1 rue de l'Exemple, 75000 Paris",
    "contact": "contact@exemple.fr",
    "site": "https://www.exemple.fr",
    "presentation": "Organisme de formation <b>fictif</b>.",
}


@pytest.fixture
def editeur(monkeypatch):
    for cle, valeur in EDITEUR.items():
        monkeypatch.setattr(reglages(), f"editeur_{cle}", valeur)


def test_a_propos_publique(client):
    page = client.get("/a-propos")
    assert page.status_code == 200
    texte = " ".join(page.text.split())
    for attendu in ("canicule", "premier tri de bureau", "preuve de concept", "Île-de-France"):
        assert attendu in texte
    assert "Qui porte le projet" not in texte  # sans éditeur configuré


def test_a_propos_avec_editeur(client, editeur):
    texte = " ".join(client.get("/a-propos").text.split())
    assert "Qui porte le projet" in texte
    assert "bitumap est porté par Camille Exemple, Exemple Formation." in texte
    assert "&lt;b&gt;fictif&lt;/b&gt;" in texte  # texte de configuration échappé
    assert '<a href="https://www.exemple.fr" rel="noopener">' in texte
    assert 'href="mailto:contact@exemple.fr"' in texte


def test_mentions_legales_sans_configuration(client):
    texte = " ".join(client.get("/mentions-legales").text.split())
    assert "Directeur de la publication" in texte and "non renseigné" in texte
    assert "Scaleway SAS" in texte and "433 115 904 RCS Paris" in texte
    assert 'href="/confidentialite"' in texte


def test_mentions_legales_avec_editeur(client, editeur):
    texte = " ".join(client.get("/mentions-legales").text.split())
    assert "Camille Exemple, Exemple Formation (EI)" in texte
    assert "SIRET : 000 000 000 00000" in texte
    assert "1 rue de l'Exemple, 75000 Paris" in texte or "1 rue de l&#39;Exemple" in texte
    assert "non renseigné" not in texte


def test_site_de_l_editeur_en_https_seulement():
    for site in ("javascript:alert(1)", "http://www.exemple.fr"):
        with pytest.raises(ValidationError):
            Reglages(editeur_site=site, db_url="postgresql://x")


def test_accueil_explique_le_projet(client):
    page = client.get("/").text
    assert 'class="presentation"' in page and 'href="/a-propos">En savoir plus' in page


@pytest.mark.parametrize("chemin", ["/", "/a-propos", "/mentions-legales", "/confidentialite"])
def test_pied_de_page(client, chemin):
    page = client.get(chemin).text
    pied = page[page.index('<footer class="pied">') :]
    for lien in ("/a-propos", "/mentions-legales", "/confidentialite"):
        assert f'href="{lien}"' in pied
