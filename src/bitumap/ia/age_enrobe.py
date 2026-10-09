"""Âge de l'enrobé des points P1 par IA vision (FR-014 ; constitution, principe V).

- P1 uniquement, après que les priorités ont été figées ;
- résultat toujours « à confirmer », avec le modèle et la date ;
- effet borné par la méthode (prototype) : réfection il y a 5 à 12 ans ×0,85, plus de 12 ans
  ×1,05, moins de 5 ans inchangé ; « marquage » ou « indéterminé » : sans effet ;
- cache par point, budget réservé avant chaque appel ; toute erreur ⇒ « non évalué ».
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from importlib import resources

from PIL import Image

from bitumap.config import reglages
from bitumap.ia import budget as budget_ia
from bitumap.ia import cache
from bitumap.ia import client as client_ia
from bitumap.journal import StatistiquesIA
from bitumap.modele import Facteur, Point
from bitumap.score.combinaison import FACTEUR_IA
from bitumap.sources.base import cause

NB_MILLESIMES_MAX = 6
EFFET_5_12_ANS = 0.85
EFFET_PLUS_12_ANS = 1.05

Vignettes = Callable[[float, float], list[tuple[int, Image.Image]]]


def prompt() -> str:
    version = reglages().ia_version_prompt
    return (resources.files("bitumap.ia") / "prompts" / f"{version}.txt").read_text("utf-8")


def choisir_millesimes(
    vignettes: list[tuple[int, Image.Image]], n: int = NB_MILLESIMES_MAX
) -> list[tuple[int, Image.Image]]:
    """Jusqu'à ``n`` millésimes répartis sur la période, dont toujours le plus récent."""
    if len(vignettes) <= n:
        return vignettes
    pas = (len(vignettes) - 1) / (n - 1)
    indices = sorted({round(i * pas) for i in range(n)})
    return [vignettes[i] for i in indices]


def facteur_depuis(reponse: client_ia.ReponseAge, annee: int, modele: str) -> Facteur:
    commun = {
        "provenance": "ia",
        "statut": "a_confirmer",
        "modele": modele,
        "date": date.today().isoformat(),
    }
    debut, fin = reponse.derniere_refection_debut, reponse.derniere_refection_fin
    if reponse.statut == "indetermine" or debut is None or fin is None:
        return Facteur(
            FACTEUR_IA,
            "indéterminé",
            1.0,
            explication=(f"Âge de l'enrobé indéterminé : {reponse.justification}"),
            visible=False,
            **commun,
        )
    age = annee - (debut + fin) / 2
    periode = f"{debut}–{fin}"
    if reponse.statut == "marquage":
        return Facteur(
            FACTEUR_IA,
            periode,
            1.0,
            explication=(f"Marquage modifié en {periode}, réfection possible (à confirmer)"),
            **commun,
        )
    if age < 5:
        effet, texte = 1.0, "Enrobé récent (moins de 5 ans) : premiers étés à surveiller"
    elif age <= 12:
        effet, texte = EFFET_5_12_ANS, f"Enrobé refait il y a {age:.0f} ans environ (×0,85)"
    else:
        effet, texte = EFFET_PLUS_12_ANS, f"Enrobé âgé d'environ {age:.0f} ans (×1,05)"
    return Facteur(FACTEUR_IA, periode, effet, explication=f"{texte} — à confirmer", **commun)


def _non_evalue(raison: str) -> Facteur:
    return Facteur(
        FACTEUR_IA,
        None,
        1.0,
        provenance="ia",
        statut="non_evalue",
        explication=f"Âge de l'enrobé non évalué ({raison})",
    )


class AnalyseurAge:
    """Appelé par ``calculer_commune`` avec les points P1 (priorités déjà figées)."""

    def __init__(
        self,
        vignettes: Vignettes,
        budget: budget_ia.BudgetRapport,
        stats: StatistiquesIA,
        appel=client_ia.analyser,
        annee: int | None = None,
        avancement: Callable[[str, int, int], None] | None = None,
    ):
        self._vignettes = vignettes
        self._avancement = avancement  # 009 : (« ia », points traités, points P1)
        self._budget = budget
        self._stats = stats
        self._appel = appel
        self._annee = annee or date.today().year
        self.bruts: dict[str, dict] = {}  # réponses brutes, écrites dans ia/{point_id}.json
        self.hors_plafond = 0  # points P1 laissés « non évalués » par un plafond de coût
        # Échecs par étape (« orthophotos », « service ») : (point, cause), signalés dans le
        # rapport et, pour le service, au mainteneur (LL-026).
        self.echecs: dict[str, list[tuple[str, str]]] = {"orthophotos": [], "service": []}
        r = reglages()
        self._modele, self._version = r.ia_modele, r.ia_version_prompt
        stats.modele, stats.version_prompt = self._modele, self._version

    def __call__(self, points_p1: list[Point]) -> None:
        if self._avancement and points_p1:
            self._avancement("ia", 0, len(points_p1))
        for k, p in enumerate(points_p1, start=1):
            p.facteurs.append(self._analyser(p))
            if self._avancement:
                self._avancement("ia", k, len(points_p1))

    def _analyser(self, p: Point) -> Facteur:
        try:
            vignettes = choisir_millesimes(self._vignettes(p.lon, p.lat))
        except Exception as erreur:
            self._stats.non_evalues += 1
            self.echecs["orthophotos"].append((p.id, cause(erreur)))
            return _non_evalue(f"orthophotos indisponibles : {cause(erreur)}")
        if len(vignettes) < 2:
            self._stats.non_evalues += 1
            return _non_evalue("moins de deux millésimes disponibles")
        millesimes = [a for a, _ in vignettes]
        en_cache = cache.lire(p.id, millesimes, self._modele, self._version)
        if en_cache is not None:
            self._stats.succes_cache += 1
            return facteur_depuis(client_ia.ReponseAge(**en_cache), self._annee, self._modele)

        reserve = budget_ia.estimation(len(vignettes), client_ia.MAX_JETONS_SORTIE)
        if not self._budget.reserver(reserve):
            self._stats.non_evalues += 1
            self.hors_plafond += 1
            return _non_evalue("plafond de coût atteint")
        try:
            appel = self._appel(prompt(), vignettes)
        except Exception as erreur:
            self._budget.ajuster(reserve, budget_ia.cout(0, 0))
            self._stats.non_evalues += 1
            self.echecs["service"].append((p.id, cause(erreur)))
            return _non_evalue(f"service indisponible : {cause(erreur)}")
        reel = budget_ia.cout(appel.jetons_entree, appel.jetons_sortie)
        self._budget.ajuster(reserve, reel)
        self._stats.appels += 1
        self._stats.jetons_entree += appel.jetons_entree
        self._stats.jetons_sortie += appel.jetons_sortie
        self._stats.cout_eur += reel
        self.bruts[p.id] = {
            "modele": self._modele,
            "version_prompt": self._version,
            "millesimes": millesimes,
            "reponse_brute": appel.brut,
        }
        if appel.reponse is None:
            self._stats.non_evalues += 1
            return _non_evalue("réponse hors schéma")
        cache.ecrire(p.id, millesimes, self._modele, self._version, appel.reponse.model_dump())
        return facteur_depuis(appel.reponse, self._annee, self._modele)
