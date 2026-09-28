"""Traitement d'une commune dans un lot : acquisition → calcul → rapport (contracts/lot-job.md).

Délai maximal par commune (FR-017) ; toute erreur est isolée à la commune (FR-007d) et le
demandeur ne reçoit qu'un message sans détail technique (FR-025).
"""

from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from bitumap import courriel, stockage
from bitumap.calcul import calculer_commune
from bitumap.config import reglages
from bitumap.ia.age_enrobe import AnalyseurAge
from bitumap.ia.budget import BudgetRapport, budget_jour_epuise
from bitumap.journal import JournalGeneration
from bitumap.lot import prise_en_charge as file
from bitumap.lot import versions
from bitumap.rapport import rendu
from bitumap.score.methode import VERSION_METHODE
from bitumap.sources.fournisseur import Fournisseur

journal = logging.getLogger("bitumap.lot")

MESSAGE_ECHEC = "La génération n'a pas abouti. Vous pouvez renouveler la demande plus tard."


class DelaiDepasse(Exception):
    pass


@contextmanager
def delai_maximal(secondes: int):
    """Interrompt le traitement au-delà du délai (signal SIGALRM, fil principal du job)."""

    def _alarme(signum, frame):
        raise DelaiDepasse

    precedent = signal.signal(signal.SIGALRM, _alarme)
    signal.alarm(secondes)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, precedent)


@dataclass
class Resultat:
    demande_id: str
    commune: str
    statut: str  # terminee, en_echec, reportee
    cout_ia: float = 0.0


def _lien_rapport(insee: str, empreinte: str) -> str:
    return f"{reglages().url_publique.rstrip('/')}/rapports/{insee}/{empreinte}"


def notifier(demande: dict, statut: str, empreinte: str | None = None) -> None:
    for email in file.demandeurs(demande["id"]):
        if statut == "terminee":
            message = courriel.rapport_pret(
                email, demande["commune_nom"], _lien_rapport(demande["commune_insee"], empreinte)
            )
        elif statut == "reportee":
            message = courriel.Courriel(
                email,
                f"Rapport reporté : {demande['commune_nom']}",
                "Le budget quotidien du service est atteint : votre demande sera traitée "
                "demain. Aucune action de votre part n'est nécessaire.",
            )
        else:
            message = courriel.rapport_en_echec(email, demande["commune_nom"])
        try:
            courriel.envoyer(message)
        except Exception:
            journal.exception("envoi de la notification impossible")


def traiter(
    demande: dict,
    lot_id: str,
    fabrique: Callable[[str], Fournisseur],
    vignettes,
    appel_ia=None,
) -> Resultat:
    ident, insee, nom = str(demande["id"]), demande["commune_insee"], demande["commune_nom"]
    if budget_jour_epuise():
        file.reporter(ident)
        notifier(demande, "reportee")
        return Resultat(ident, nom, "reportee")

    empreinte = versions.empreinte_courante(insee)
    if stockage.rapport_complet(insee, empreinte):  # produit entre-temps par une autre demande
        file.terminer(ident, empreinte)
        notifier(demande, "terminee", empreinte)
        return Resultat(ident, nom, "terminee")

    jg = JournalGeneration(insee, VERSION_METHODE, lot_id=lot_id)
    budget = BudgetRapport()
    kwargs = {} if appel_ia is None else {"appel": appel_ia}
    analyseur = AnalyseurAge(vignettes, budget, jg.ia, **kwargs)
    try:
        with delai_maximal(reglages().commune_delai_max_min * 60):
            file.etape(ident, "acquisition")
            fournisseur = fabrique(insee)
            file.etape(ident, "calcul")
            with jg.chronometrer("calcul"):
                resultat = calculer_commune(fournisseur, nom, analyse_ia=analyseur)
            file.etape(ident, "rapport")
            with jg.chronometrer("rapport"):
                jg.nb_points = len(resultat.points)
                jg.avertissements = resultat.avertissements
                jg.terminer()
                stockage.ecrire_rapport(
                    insee, empreinte, rendu.rendre(resultat, jg, analyseur.bruts)
                )
    except DelaiDepasse:
        journal.error("commune %s : délai maximal dépassé", insee)
        file.echouer(ident, "La génération a dépassé la durée maximale.")
        notifier(demande, "en_echec")
        return Resultat(ident, nom, "en_echec", float(budget.depense))
    except Exception:
        journal.exception("commune %s : échec", insee)  # détail dans le journal (FR-025)
        file.echouer(ident, MESSAGE_ECHEC)
        notifier(demande, "en_echec")
        return Resultat(ident, nom, "en_echec", float(budget.depense))
    finally:
        closer = getattr(locals().get("fournisseur"), "fermer", None)
        if closer:
            closer()
    file.terminer(ident, empreinte)
    notifier(demande, "terminee", empreinte)
    return Resultat(ident, nom, "terminee", float(budget.depense))
