"""Traitement d'une commune dans un lot : acquisition → calcul → rapport (contracts/lot-job.md).

Délai maximal par commune (FR-017) ; toute erreur est isolée à la commune (FR-007d) et le
demandeur ne reçoit qu'un message sans détail technique (FR-025).
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from bitumap import courriel, stockage
from bitumap.calcul import calculer_commune, regrouper
from bitumap.config import reglages
from bitumap.ia.age_enrobe import AnalyseurAge
from bitumap.ia.budget import (
    BudgetRapport,
    alerter_budget_jour,
    alerter_une_fois,
    budget_jour_epuise,
)
from bitumap.journal import JournalGeneration, evenement
from bitumap.lot import prise_en_charge as file
from bitumap.lot import versions
from bitumap.lot.progression import Progression
from bitumap.rapport import rendu
from bitumap.score.comparaison import calculer_avec_v1
from bitumap.score.methode import VERSION_METHODE, version_appliquee
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


class _Chronometre:
    """Enveloppe d'un objet : cumule dans ``durees_s[etape]`` le temps passé dans ses
    méthodes (sources acquises à la demande pendant le calcul, analyses IA)."""

    def __init__(self, cible, journal: JournalGeneration, etape: str):
        self._cible, self._journal, self._etape = cible, journal, etape

    def _mesurer(self, fonction, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return fonction(*args, **kwargs)
        finally:
            durees = self._journal.durees_s
            durees[self._etape] = round(durees.get(self._etape, 0) + time.perf_counter() - t0, 3)

    def __call__(self, *args, **kwargs):
        return self._mesurer(self._cible, *args, **kwargs)

    def __getattr__(self, nom):
        attribut = getattr(self._cible, nom)
        if not callable(attribut):
            return attribut
        return lambda *args, **kwargs: self._mesurer(attribut, *args, **kwargs)


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


def _signaler_echecs_ia(analyseur: AnalyseurAge, avertissements: list[str], insee: str) -> None:
    """Échecs de l'âge de l'enrobé visibles dans le rapport ; panne du service d'IA signalée
    au mainteneur, une fois par jour (LL-026 : 403 passés inaperçus en production)."""
    ortho, service = analyseur.echecs["orthophotos"], analyseur.echecs["service"]
    if ortho:
        avertissements.append(regrouper("Âge de l'enrobé non évalué : orthophotos IGN", ortho))
    if not service:
        return
    avertissements.append(regrouper("Âge de l'enrobé non évalué : service d'IA", service))
    try:
        alerter_une_fois(
            f"ia_indisponible:{time.strftime('%Y-%m-%d')}",
            "service d'IA indisponible",
            f"Commune {insee} : {len(service)} appel(s) en échec "
            f"({', '.join(sorted({c for _, c in service}))}). Voir le journal (Cockpit).",
        )
    except Exception:
        journal.exception("alerte « service d'IA indisponible » impossible")


def traiter(
    demande: dict,
    lot_id: str,
    fabrique: Callable[[str], Fournisseur],
    vignettes,
    appel_ia=None,
) -> Resultat:
    ident, insee, nom = str(demande["id"]), demande["commune_insee"], demande["commune_nom"]
    if budget_jour_epuise():
        alerter_budget_jour()
        file.reporter(ident)
        notifier(demande, "reportee")
        evenement(journal, "commune.reportee", insee=insee, raison="budget IA du jour")
        return Resultat(ident, nom, "reportee")

    empreinte = versions.empreinte_courante(insee)
    if stockage.rapport_complet(insee, empreinte):  # produit entre-temps par une autre demande
        file.terminer(ident, empreinte)
        notifier(demande, "terminee", empreinte)
        return Resultat(ident, nom, "terminee")

    jg = JournalGeneration(insee, version_appliquee(), lot_id=lot_id)
    budget = BudgetRapport()
    # Avancement affiché sur la page de suivi (009) ; ne fait jamais échouer la génération.
    progression = Progression(lambda etape, pct, fin: file.avancer(ident, etape, pct, fin))
    kwargs = {} if appel_ia is None else {"appel": appel_ia}
    analyseur = AnalyseurAge(vignettes, budget, jg.ia, avancement=progression, **kwargs)
    try:
        with delai_maximal(reglages().commune_delai_max_min * 60):
            fournisseur = _Chronometre(fabrique(insee), jg, "acquisition")
            with jg.chronometrer("calcul"):
                # 2.0 : la commune est aussi calculée en 1.2 pour expliquer les changements
                # de niveau (004 R6), sur les mêmes sources et réponses d'IA.
                calcul = (
                    calculer_commune if jg.version_methode == VERSION_METHODE else calculer_avec_v1
                )
                resultat = calcul(
                    fournisseur,
                    nom,
                    analyse_ia=_Chronometre(analyseur, jg, "ia"),
                    avancement=progression,
                )
            # Temps propre du calcul : sans l'acquisition des sources ni l'IA.
            jg.durees_s["calcul"] = round(
                jg.durees_s["calcul"]
                - jg.durees_s.get("acquisition", 0)
                - jg.durees_s.get("ia", 0),
                3,
            )
            if analyseur.hors_plafond:
                resultat.avertissements.append(
                    f"Plafond de coût de l'IA atteint : âge de l'enrobé non évalué pour "
                    f"{analyseur.hors_plafond} point(s) prioritaire(s)."
                )
            _signaler_echecs_ia(analyseur, resultat.avertissements, insee)
            progression("rapport", 0, 1)
            with jg.chronometrer("rapport"):
                jg.nb_points = len(resultat.points)
                jg.avertissements = resultat.avertissements
                fichiers = rendu.rendre(resultat, jg, analyseur.bruts)
            jg.terminer()
            # journal.json régénéré pour contenir la durée de l'étape « rapport »
            fichiers["journal.json"] = (jg.en_json(), fichiers["journal.json"][1])
            stockage.ecrire_rapport(insee, empreinte, fichiers)
    except DelaiDepasse:
        evenement(journal, "commune.en_echec", logging.ERROR, insee=insee, raison="délai")
        file.echouer(ident, "La génération a dépassé la durée maximale.")
        notifier(demande, "en_echec")
        return Resultat(ident, nom, "en_echec", float(budget.depense))
    except Exception as erreur:
        journal.exception("commune %s : échec", insee)  # détail dans le journal (FR-025)
        evenement(
            journal, "commune.en_echec", logging.ERROR, insee=insee, raison=type(erreur).__name__
        )
        file.echouer(ident, MESSAGE_ECHEC)
        notifier(demande, "en_echec")
        return Resultat(ident, nom, "en_echec", float(budget.depense))
    finally:
        closer = getattr(locals().get("fournisseur"), "fermer", None)
        if closer:
            closer()
    file.terminer(ident, empreinte)
    notifier(demande, "terminee", empreinte)
    evenement(
        journal,
        "commune.terminee",
        insee=insee,
        empreinte=empreinte,
        nb_points=jg.nb_points,
        durees_s=jg.durees_s,
        ia_appels=jg.ia.appels,
        ia_cout_eur=float(jg.ia.cout_eur),
        ia_non_evalues=jg.ia.non_evalues,
        avertissements=len(jg.avertissements),
    )
    return Resultat(ident, nom, "terminee", float(budget.depense))
