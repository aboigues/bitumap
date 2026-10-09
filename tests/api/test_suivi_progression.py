"""Progression de la génération sur les pages de suivi et « Mes demandes » (009, contrat
§3) : sans script, rechargement de la page, jamais 100 %, durée restante."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from bitumap.db import connexion
from tests.conftest import connecter, preuve


def _demande(client, courriels, email="agent@exemple.fr"):
    csrf = connecter(client, courriels, email)
    reponse = client.post(
        "/demandes",
        data={"insee": "92026", "csrf": csrf, "altcha": preuve(client)},
        follow_redirects=False,
    )
    lien = reponse.headers["location"]
    return lien, lien.rsplit("/", 1)[1]


def _etat(ident, **colonnes):
    valeurs = {"etat": "en_cours", "etape": None, "avancement": None, "fin_estimee": None}
    valeurs.update(colonnes)
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = %s, etape = %s, avancement = %s, fin_estimee = %s"
            " WHERE id = %s",
            (
                valeurs["etat"],
                valeurs["etape"],
                valeurs["avancement"],
                valeurs["fin_estimee"],
                ident,
            ),
        )


def _rafraichissement(page: str) -> str | None:
    trouve = re.search(r'http-equiv="refresh" content="(\d+)"', page)
    return trouve.group(1) if trouve else None


def test_pourcentage_barre_et_phase(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etape="ia", avancement=42)
    page = client.get(lien).text
    assert "<strong>42 %</strong> — analyse des photos aériennes" in page
    assert '<progress max="100" value="42" aria-label="Avancement de la génération">' in page
    assert _rafraichissement(page) == "15"
    assert "<script" not in page.split("<main", 1)[-1]


def test_demarrage_sans_avancement(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident)
    page = client.get(lien).text
    assert "démarrage" in page and "<progress" not in page


def test_etape_ancienne(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etape="calcul")  # ligne écrite par une version antérieure du job
    page = client.get(lien).text
    assert "génération en cours" in page and "<progress" not in page


def test_en_file_inchange(client, courriels, territoire, s3):
    lien, _ = _demande(client, courriels)
    page = client.get(lien).text
    assert "file d'attente" in page and _rafraichissement(page) == "30"
    assert "<progress" not in page


def test_terminee_jamais_cent(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etat="terminee")
    page = client.get(lien).text
    assert "Ouvrir le rapport" in page and "100 %" not in page
    assert _rafraichissement(page) is None


def test_liste_mes_demandes(client, courriels, territoire, s3):
    _, ident = _demande(client, courriels)
    _etat(ident, etape="points", avancement=12)
    assert "en cours (12 %)" in client.get("/demandes").text
    _etat(ident)
    page = client.get("/demandes").text
    assert "en cours" in page and "%)" not in page


def test_autre_compte_ne_voit_pas_l_avancement(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels, "a@exemple.fr")
    _etat(ident, etape="ia", avancement=42)
    client.cookies.clear()
    connecter(client, courriels, "b@exemple.fr")
    assert client.get(lien).status_code == 404


def _maintenant_plus(secondes: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=secondes)


def test_duree_restante_arrondie_a_la_minute_superieure(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etape="ia", avancement=60, fin_estimee=_maintenant_plus(190))
    assert "Environ 4 min restantes." in client.get(lien).text


def test_moins_d_une_minute(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etape="ia", avancement=95, fin_estimee=_maintenant_plus(40))
    assert "Moins d'une minute." in client.get(lien).text


def test_pas_de_duree_passee_ou_absente(client, courriels, territoire, s3):
    lien, ident = _demande(client, courriels)
    _etat(ident, etape="ia", avancement=95, fin_estimee=_maintenant_plus(-30))
    page = client.get(lien).text
    assert "restante" not in page and "Moins d'une minute" not in page
    _etat(ident, etape="points", avancement=10)
    assert "restante" not in client.get(lien).text


def test_minutes_restantes(monkeypatch):
    from bitumap.api import demandes

    fixe = datetime(2026, 10, 9, 12, tzinfo=UTC)

    class Horloge(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixe

    monkeypatch.setattr(demandes, "datetime", Horloge)
    plus = lambda s: fixe + timedelta(seconds=s)  # noqa: E731
    assert demandes.minutes_restantes(None) is None
    assert demandes.minutes_restantes(plus(-1)) is None
    assert demandes.minutes_restantes(plus(0)) is None
    assert demandes.minutes_restantes(plus(59)) == 0
    assert demandes.minutes_restantes(plus(60)) == 1
    assert demandes.minutes_restantes(plus(61)) == 2
    assert demandes.minutes_restantes(plus(190)) == 4


def test_pages_avant_la_migration_du_job(client, courriels, territoire, s3, monkeypatch):
    """API déployée avant le premier passage du job : colonnes absentes (R7)."""
    from bitumap.api import demandes

    lien, ident = _demande(client, courriels)
    _etat(ident, etape="calcul")
    origine = demandes.connexion

    class SansColonnes:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, *args, **kwargs):
            curseur = self._conn.execute(*args, **kwargs)
            return _Curseur(curseur)

    class _Curseur:
        def __init__(self, curseur):
            self._c = curseur

        def _retirer(self, ligne):
            if ligne is None:
                return None
            return {k: v for k, v in ligne.items() if k not in ("avancement", "fin_estimee")}

        def fetchone(self):
            return self._retirer(self._c.fetchone())

        def fetchall(self):
            return [self._retirer(li) for li in self._c.fetchall()]

    from contextlib import contextmanager

    @contextmanager
    def connexion_ancienne():
        with origine() as conn:
            yield SansColonnes(conn)

    monkeypatch.setattr(demandes, "connexion", connexion_ancienne)
    assert "génération en cours" in client.get(lien).text
    liste = client.get("/demandes").text
    assert "en cours" in liste and "%)" not in liste
