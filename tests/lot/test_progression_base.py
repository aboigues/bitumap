"""Avancement de la demande en base (009, data-model : transitions)."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from bitumap.db import connexion
from bitumap.lot import prise_en_charge as file
from tests.lot.test_lot import _demande, _etat

FIN = datetime(2026, 10, 9, 12, 30, tzinfo=UTC)


def _en_cours(ident, etape=None, avancement=None, fin_estimee=None, tentatives=0):
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'en_cours', pris_en_charge_le = now(), etape = %s,"
            " avancement = %s, fin_estimee = %s, tentatives = %s WHERE id = %s",
            (etape, avancement, fin_estimee, tentatives, ident),
        )


def test_avancer_enregistre_phase_pourcentage_et_fin(base):
    ident = _demande()
    _en_cours(ident)
    file.avancer(ident, "ia", 42, FIN)
    etat = _etat(ident)
    assert (etat["etape"], etat["avancement"], etat["fin_estimee"]) == ("ia", 42, FIN)


def test_avancement_jamais_en_recul(base):
    ident = _demande()
    _en_cours(ident)
    file.avancer(ident, "ia", 60, None)
    file.avancer(ident, "ia", 40, None)  # passe 1.2 de la méthode 2.0, écriture tardive
    assert _etat(ident)["avancement"] == 60


def test_aucune_ecriture_hors_generation(base):
    ident = _demande()  # en file
    file.avancer(ident, "points", 10, None)
    etat = _etat(ident)
    assert etat["avancement"] is None and etat["etape"] is None


@pytest.mark.parametrize(
    "transition",
    [
        lambda i: file.terminer(i, "e92026"),
        lambda i: file.echouer(i, "Échec."),
        file.reporter,
    ],
)
def test_avancement_efface_en_sortie_de_generation(base, transition):
    ident = _demande()
    _en_cours(ident, etape="ia", avancement=50, fin_estimee=FIN)
    transition(ident)
    etat = _etat(ident)
    assert etat["avancement"] is None and etat["fin_estimee"] is None


@pytest.mark.parametrize("tentatives", [0, 2])  # remise en file, puis échec définitif
def test_avancement_efface_a_la_reprise(base, tentatives):
    ident = _demande()
    _en_cours(ident, etape="ia", avancement=50, fin_estimee=FIN, tentatives=tentatives)
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET pris_en_charge_le = %s WHERE id = %s",
            (datetime.now(UTC) - timedelta(hours=4), ident),
        )
    file.reprendre_les_lots_interrompus()
    etat = _etat(ident)
    assert etat["avancement"] is None and etat["fin_estimee"] is None


def test_cent_pour_cent_refuse_par_la_base(base):
    ident = _demande()
    _en_cours(ident)
    with pytest.raises(psycopg.errors.CheckViolation):
        file.avancer(ident, "rapport", 100, None)


def test_generation_reelle_enregistre_un_avancement_croissant(base, s3, monkeypatch):
    """Lot complet sur Courbevoie (données figées, IA simulée) : relevés croissants de la
    demande pendant la génération, phases dans l'ordre, rien de laissé à la fin."""
    from bitumap.lot import progression
    from tests.lot.aides import executer_lot

    releves: list[tuple[str, int]] = []
    avancer = file.avancer

    def espion(ident, etape, pct, fin):
        avancer(ident, etape, pct, fin)
        etat = _etat(ident)
        releves.append((etat["etape"], etat["avancement"]))

    monkeypatch.setattr(file, "avancer", espion)
    monkeypatch.setattr(progression, "CADENCE_S", 0.0)  # toutes les écritures
    ident = _demande(compte="agent@exemple.fr")
    executer_lot()
    valeurs = [a for _, a in releves]
    assert valeurs == sorted(valeurs) and valeurs[-1] == 97
    phases = list(dict.fromkeys(e for e, _ in releves))
    assert phases == ["sources", "points", "ia", "rapport"]
    etat = _etat(ident)
    assert etat["etat"] == "terminee" and etat["avancement"] is None
