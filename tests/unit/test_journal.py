"""Coûts et suivi (US4 : FR-023, FR-024, FR-029 ; T069, T070, T071, T091).

Lot réel sur les données figées de Courbevoie, IA simulée (1 500 + 80 jetons par appel,
soit environ 0,00025 € au tarif par défaut).
"""

import json
import logging
from decimal import Decimal

from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.ia import budget
from bitumap.journal import FormatJson, evenement
from tests.lot.aides import executer_lot
from tests.lot.test_lot import _demande, _etat

PLAFOND_SERRE = Decimal("0.002")  # quelques appels seulement sur les 31 P1


def _fichier(s3, ident, nom):
    empreinte = _etat(ident)["empreinte"]
    cle = f"communes/92026/{empreinte}/{nom}"
    return s3.get_object(Bucket="bitumap-rapports", Key=cle)["Body"].read().decode()


def _depense_du_jour() -> Decimal:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT montant_eur FROM cout_ia_jour WHERE jour = current_date"
        ).fetchone()
    return Decimal(ligne["montant_eur"]) if ligne else Decimal(0)


def test_plafond_par_rapport_atteint(base, s3, courriels, monkeypatch):
    """US4-2 : rapport produit, P1 « âge non évalué », avertissement, aucune dépense
    au-delà du plafond."""
    monkeypatch.setattr(reglages(), "ia_plafond_rapport_eur", PLAFOND_SERRE)
    ident = _demande(compte="a@exemple.fr")
    resultat = executer_lot()[0]
    assert resultat.statut == "terminee"
    assert Decimal(str(resultat.cout_ia)) <= PLAFOND_SERRE
    assert _depense_du_jour() <= PLAFOND_SERRE

    journal = json.loads(_fichier(s3, ident, "journal.json"))
    assert 0 < journal["ia"]["appels"] < 31
    assert journal["ia"]["non_evalues"] >= 31 - journal["ia"]["appels"]
    assert any("Plafond de coût de l'IA atteint" in a for a in journal["avertissements"])

    points = json.loads(_fichier(s3, ident, "points.geojson"))["features"]
    ages = [
        f
        for p in points
        if p["properties"]["priorite"] == "P1"
        for f in p["properties"]["facteurs"]
        if f["nom"] == "age_enrobe"
    ]
    assert any("plafond de coût atteint" in f["explication"] for f in ages)
    assert "Plafond de coût de l&#39;IA atteint" in _fichier(s3, ident, "rapport.html")


def test_plafond_nul_aucun_appel(base, s3, monkeypatch):
    monkeypatch.setattr(reglages(), "ia_plafond_rapport_eur", Decimal(0))
    ident = _demande()
    appels = []
    executer_lot(appel_ia=lambda *a: appels.append(a))
    assert appels == [] and _depense_du_jour() == 0
    assert json.loads(_fichier(s3, ident, "journal.json"))["ia"]["appels"] == 0


def test_journal_complet_sans_donnee_personnelle(base, s3):
    ident = _demande(compte="agent@exemple.fr")
    executer_lot()
    journal = json.loads(_fichier(s3, ident, "journal.json"))
    assert set(journal["durees_s"]) == {"acquisition", "calcul", "ia", "rapport"}
    assert all(v >= 0 for v in journal["durees_s"].values())
    assert journal["nb_points"] == 154
    assert journal["ia"]["modele"] and journal["ia"]["jetons_entree"] > 0
    assert journal["lot_id"] and journal["version_methode"]
    texte = json.dumps(journal)
    assert "agent@exemple.fr" not in texte and "compte" not in texte


def test_statistiques_du_lot_en_base(base, s3):
    from tests.lot.aides import fabrique_figee

    def fabrique(insee):
        if insee == "92004":
            raise ConnectionError("source indisponible")
        return fabrique_figee(insee)

    _demande()
    _demande(insee="92004", nom="Asnières-sur-Seine", empreinte="asnieres")
    executer_lot(fabrique=fabrique)
    with connexion() as conn:
        lot = conn.execute("SELECT * FROM lot WHERE nb_demandes > 0").fetchone()
    assert (lot["nb_terminees"], lot["nb_echecs"], lot["nb_reportees"]) == (1, 1, 0)
    assert lot["termine_le"] and lot["cout_ia_eur"] > 0


def test_alerte_budget_du_jour_une_seule_fois(base, s3, courriels, monkeypatch):
    monkeypatch.setattr(reglages(), "email_mainteneur", "mainteneur@exemple.fr")
    monkeypatch.setattr(reglages(), "ia_plafond_jour_eur", PLAFOND_SERRE)
    _demande()
    executer_lot()
    _demande(insee="92026", nom="Courbevoie", empreinte="autre")  # reportée : même alerte
    executer_lot()
    alertes = [c for c in courriels if "plafond IA du jour atteint" in c.sujet]
    assert len(alertes) == 1 and alertes[0].destinataire == "mainteneur@exemple.fr"
    assert _depense_du_jour() <= PLAFOND_SERRE


def test_alerte_budget_sans_destinataire_configure(base, courriels, monkeypatch):
    monkeypatch.setattr(reglages(), "email_mainteneur", None)
    assert budget.alerter_budget_jour() is True  # enregistrée, mais aucun e-mail
    assert courriels == []


def test_alerte_erreur_d_infrastructure(base, courriels, monkeypatch):
    from bitumap.lot import __main__ as lot

    monkeypatch.setattr(reglages(), "email_mainteneur", "mainteneur@exemple.fr")

    def panne(*_):
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(lot, "executer", panne)
    assert lot.main([]) == 1
    assert lot.main([]) == 1  # même heure : pas de seconde alerte
    alertes = [c for c in courriels if c.sujet.startswith("[bitumap] lot interrompu")]
    assert len(alertes) == 1 and "ConnectionError" in alertes[0].sujet


def test_journal_structure_json():
    enregistrements = []

    class Capture(logging.Handler):
        def emit(self, record):
            enregistrements.append(FormatJson().format(record))

    journal = logging.getLogger("bitumap.test_journal")
    journal.addHandler(Capture())
    journal.setLevel(logging.INFO)
    evenement(journal, "commune.terminee", insee="92026", durees_s={"calcul": 1.5})
    ligne = json.loads(enregistrements[-1])
    assert ligne["evenement"] == ligne["message"] == "commune.terminee"
    assert ligne["insee"] == "92026" and ligne["durees_s"] == {"calcul": 1.5}
    assert ligne["niveau"] == "INFO" and ligne["horodatage"]
