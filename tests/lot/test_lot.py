"""Job de lot (contracts/lot-job.md ; FR-007a à FR-007d, FR-017, SC-008)."""

import threading
import time
from datetime import date

from bitumap.db import connexion
from bitumap.lot import prise_en_charge as file
from bitumap.lot import versions
from bitumap.lot.__main__ import executer
from bitumap.sources.fournisseur import FournisseurFige
from tests.lot.aides import FIXTURES, executer_lot


def _demande(insee="92026", nom="Courbevoie", empreinte=None, compte=None):
    with connexion() as conn:
        ident = conn.execute(
            "INSERT INTO demande (commune_insee, commune_nom, empreinte) VALUES (%s, %s, %s)"
            " RETURNING id",
            (insee, nom, empreinte or f"e{insee}"),
        ).fetchone()["id"]
        if compte:
            cid = conn.execute(
                "INSERT INTO compte (email) VALUES (%s) RETURNING id", (compte,)
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO demandeur_demande (demande_id, compte_id, compte_quota)"
                " VALUES (%s, %s, true)",
                (ident, cid),
            )
    return str(ident)


def _etat(ident):
    with connexion() as conn:
        return conn.execute("SELECT * FROM demande WHERE id = %s", (ident,)).fetchone()


def test_file_vide_fin_rapide(base):
    t0 = time.perf_counter()
    assert executer(regional_fn=lambda d: (_ for _ in ()).throw(AssertionError)) == []
    assert time.perf_counter() - t0 < 30  # SC-008


def test_deux_lots_ne_prennent_jamais_la_meme_demande(base):
    idents = {_demande(f"9202{i}", empreinte=f"e{i}") for i in range(8)}
    pris: list[list[dict]] = []

    def lot():
        pris.append(file.prendre(file.ouvrir_lot(), taille=8))

    fils = [threading.Thread(target=lot) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    ensemble = [str(d["id"]) for lot_ in pris for d in lot_]
    assert sorted(ensemble) == sorted(idents)  # chaque demande prise une seule fois


def test_taille_de_lot_limitee(base):
    for i in range(12):
        _demande(f"9{i:04d}", empreinte=f"x{i}")
    assert len(file.prendre(file.ouvrir_lot())) == 10


def test_echec_isole_a_une_commune(base, s3, courriels):
    bonne = _demande("92026", "Courbevoie", compte="a@exemple.fr")
    mauvaise = _demande("99001", "Inconnue", compte="b@exemple.fr")

    def fabrique(insee):
        if insee == "99001":
            raise RuntimeError("source indisponible")
        return FournisseurFige(FIXTURES, insee)

    resultats = executer_lot(fabrique=fabrique)
    statuts = {r.demande_id: r.statut for r in resultats}
    assert statuts == {bonne: "terminee", mauvaise: "en_echec"}
    assert "source" not in (_etat(mauvaise)["erreur_publique"] or "")  # aucun détail technique
    assert any(c.sujet.startswith("Rapport non généré") for c in courriels)


def test_reprise_apres_lot_interrompu(base):
    ident = _demande()
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'en_cours', pris_en_charge_le = now() - interval '4 hours'"
            " WHERE id = %s",
            (ident,),
        )
    assert file.reprendre_les_lots_interrompus() == 1
    etat = _etat(ident)
    assert etat["etat"] == "en_file" and etat["tentatives"] == 1


def test_echec_definitif_apres_deux_tentatives(base):
    ident = _demande()
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'en_cours', tentatives = 2,"
            " pris_en_charge_le = now() - interval '4 hours' WHERE id = %s",
            (ident,),
        )
    file.reprendre_les_lots_interrompus()
    assert _etat(ident)["etat"] == "en_echec"


def test_budget_du_jour_epuise_reporte(base, s3, courriels):
    ident = _demande(compte="a@exemple.fr")
    with connexion() as conn:
        conn.execute("INSERT INTO cout_ia_jour (jour, montant_eur) VALUES (current_date, 999)")
    resultats = executer_lot()
    assert resultats[0].statut == "reportee"
    etat = _etat(ident)
    assert etat["etat"] == "en_file" and etat["reportee"]
    assert any(c.sujet.startswith("Rapport reporté") for c in courriels)


def test_commune_sans_ligne_de_bus(base, s3, courriels):
    class SansBus(FournisseurFige):
        def offre(self):
            prov, _ = super().offre()
            return prov, []

    ident = _demande(compte="a@exemple.fr")
    resultats = executer_lot(fabrique=lambda insee: SansBus(FIXTURES, insee))
    assert resultats[0].statut == "terminee"
    etat = _etat(ident)
    contenu = (
        s3.get_object(
            Bucket="bitumap-rapports", Key=f"communes/92026/{etat['empreinte']}/rapport.html"
        )["Body"]
        .read()
        .decode()
    )
    assert "Aucun point à relever" in contenu


def test_rapport_complet_et_empreinte(base, s3):
    ident = _demande()
    executer_lot()
    etat = _etat(ident)
    assert etat["etat"] == "terminee"
    assert etat["empreinte"] == versions.empreinte_courante("92026")
    cles = {
        o["Key"].split("/", 3)[3] for o in s3.list_objects_v2(Bucket="bitumap-rapports")["Contents"]
    }
    assert {"rapport.html", "points.geojson", "sources.json", "journal.json"} <= cles
    assert any(c.startswith("ia/") for c in cles)  # réponses IA brutes conservées


def test_versions_enregistrees(base):
    versions.enregistrer("osm", date(2026, 9, 27))
    versions.enregistrer("osm", date(2026, 10, 4))
    assert versions.courantes()["osm"] == date(2026, 10, 4)


def test_ia_indisponible_signalee(base, s3, courriels, monkeypatch):
    # LL-026 : en production, toutes les analyses ont échoué (403) sans aucun signalement.
    from bitumap import courriel
    from bitumap.config import reglages

    monkeypatch.setattr(reglages(), "email_mainteneur", "mainteneur@exemple.fr")

    def appel_refuse(prompt, vignettes):
        raise PermissionError("403")

    ident = _demande()
    executer_lot(appel_ia=appel_refuse)
    etat = _etat(ident)
    journal = (
        s3.get_object(
            Bucket="bitumap-rapports", Key=f"communes/92026/{etat['empreinte']}/journal.json"
        )["Body"]
        .read()
        .decode()
    )
    assert "service d'IA" in journal and "PermissionError" in journal
    alertes = [m for m in courriel.ENVOYES if "service d'IA indisponible" in m.sujet]
    assert len(alertes) == 1 and alertes[0].destinataire == "mainteneur@exemple.fr"


def test_alerte_ia_une_fois_par_jour(base, courriels, monkeypatch):
    from bitumap import courriel
    from bitumap.config import reglages
    from bitumap.lot.commune import _signaler_echecs_ia

    monkeypatch.setattr(reglages(), "email_mainteneur", "mainteneur@exemple.fr")

    from types import SimpleNamespace

    analyseur = SimpleNamespace(
        echecs={"orthophotos": [], "service": [("A1", "PermissionDeniedError")]}
    )
    for insee in ("92026", "92004"):  # deux communes du même jour
        _signaler_echecs_ia(analyseur, [], insee)
    assert sum("service d'IA" in m.sujet for m in courriel.ENVOYES) == 1


def test_orthophotos_indisponibles_signalees_dans_le_rapport(base, s3):
    from bitumap.sources.base import SourceIndisponible

    def vignettes_en_echec(lon, lat):
        raise SourceIndisponible("Orthophotos IGN", "HTTP 429")

    ident = _demande()
    executer_lot(vignettes=vignettes_en_echec)
    etat = _etat(ident)
    journal = (
        s3.get_object(
            Bucket="bitumap-rapports", Key=f"communes/92026/{etat['empreinte']}/journal.json"
        )["Body"]
        .read()
        .decode()
    )
    assert "orthophotos IGN" in journal and "HTTP 429" in journal
