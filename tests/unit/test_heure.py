"""Heure affichée en heure de Paris, le serveur étant en UTC (anomalie 2 du 2026-10-07)."""

from datetime import UTC, datetime

from bitumap import heure


def test_instant_utc_affiche_en_heure_de_paris():
    ete = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    hiver = datetime(2026, 12, 7, 12, 0, tzinfo=UTC)
    assert heure.formater(ete, "%H:%M") == "14:00"  # UTC+2
    assert heure.formater(hiver, "%H:%M") == "13:00"  # UTC+1


def test_chaine_iso_et_valeur_sans_fuseau_lues_comme_utc():
    assert heure.formater("2026-10-07T22:30:00+00:00") == "08/10/2026 00:30"
    assert heure.formater(datetime(2026, 10, 7, 22, 30)) == "08/10/2026 00:30"
    assert heure.formater(None) == ""


def test_filtre_des_gabarits():
    from bitumap.api.application import gabarits

    modele = gabarits.env.from_string('{{ t|heure("%d/%m %H:%M") }}')
    assert modele.render(t=datetime(2026, 10, 7, 22, 30, tzinfo=UTC)) == "08/10 00:30"
