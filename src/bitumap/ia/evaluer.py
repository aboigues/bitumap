"""Évaluation comparative des modèles vision (T072, research R7, SC-012).

Usage :
  uv run python -m bitumap.ia.evaluer --echantillon tests/fixtures/ia/echantillon_30.json \
      [--modeles m1 m2 …] [--sortie evaluation.md]

Échantillon (T073, constitué avec le mainteneur) : ``{"points": [{"id", "nom", "lon", "lat",
"refection_annee", "source"}]}``, points P1 dont l'année de la dernière réfection est connue.

Pour chaque modèle : mêmes orthophotos et même prompt que le service ; une période est
**bonne** si l'année réelle est dans la période répondue (SC-012 : ≥ 70 %) ; la **classe
d'effet** (moins de 5 ans, 5 à 12 ans, plus de 12 ans) est celle qui compte pour le score.
Coût réel à partir des jetons consommés et du tarif du modèle. Décision R7 : le plus exact,
puis le moins cher en cas d'égalité.

Appels réels (clé ``BITUMAP_GENAI_CLE``, orthophotos IGN) : lancé par le mainteneur, jamais
en CI.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from bitumap.ia import client as client_ia
from bitumap.ia.age_enrobe import (
    EFFET_5_12_ANS,
    EFFET_PLUS_12_ANS,
    Vignettes,
    choisir_millesimes,
    prompt,
)

MODELES = ("mistral-medium-3.5-128b", "mistral-small-3.2-24b-instruct-2506", "qwen3.8-27b")
# € par million de jetons (entrée, sortie), tarifs Scaleway relevés le 2026-09-28 (R7-bis).
TARIFS = {
    "mistral-medium-3.5-128b": (Decimal("1.50"), Decimal("7.50")),
    "mistral-small-3.2-24b-instruct-2506": (Decimal("0.15"), Decimal("0.35")),
    "qwen3.8-27b": (Decimal("0.60"), Decimal("3.30")),
}
SEUIL_SC012 = 0.70


def classe(age: float) -> str:
    return "moins de 5 ans" if age < 5 else ("5 à 12 ans" if age <= 12 else "plus de 12 ans")


@dataclass
class Mesure:
    point_id: str
    verite: int
    periode: tuple[int, int] | None = None
    statut: str = "non_evalue"
    bonne_periode: bool = False
    bonne_classe: bool = False
    jetons_entree: int = 0
    jetons_sortie: int = 0
    duree_s: float = 0.0
    erreur: str = ""


@dataclass
class Bilan:
    modele: str
    mesures: list[Mesure] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.mesures)

    def taux(self, attribut: str) -> float:
        return sum(getattr(m, attribut) for m in self.mesures) / self.n if self.n else 0.0

    @property
    def non_evalues(self) -> int:
        return sum(m.periode is None for m in self.mesures)

    @property
    def cout_eur(self) -> Decimal:
        entree, sortie = TARIFS.get(self.modele, (Decimal(0), Decimal(0)))
        jetons_e = sum(m.jetons_entree for m in self.mesures)
        jetons_s = sum(m.jetons_sortie for m in self.mesures)
        return (jetons_e * entree + jetons_s * sortie) / Decimal(1_000_000)


def evaluer_point(
    point: dict, modele: str, vignettes: Vignettes, appel: Callable, annee: int
) -> Mesure:
    verite = int(point["refection_annee"])
    mesure = Mesure(point["id"], verite)
    try:
        images = choisir_millesimes(vignettes(point["lon"], point["lat"]))
        t0 = time.perf_counter()
        resultat = appel(prompt(), images, modele=modele)
        mesure.duree_s = time.perf_counter() - t0
    except Exception as erreur:  # un point en erreur n'arrête pas l'évaluation
        mesure.erreur = type(erreur).__name__
        return mesure
    mesure.jetons_entree, mesure.jetons_sortie = resultat.jetons_entree, resultat.jetons_sortie
    reponse = resultat.reponse
    if reponse is None:
        mesure.erreur = "réponse hors schéma"
        return mesure
    mesure.statut = reponse.statut
    debut, fin = reponse.derniere_refection_debut, reponse.derniere_refection_fin
    if reponse.statut == "indetermine" or debut is None or fin is None:
        return mesure
    mesure.periode = (debut, fin)
    mesure.bonne_periode = debut <= verite <= fin
    mesure.bonne_classe = classe(annee - (debut + fin) / 2) == classe(annee - verite)
    return mesure


def evaluer(
    echantillon: list[dict],
    modeles: tuple[str, ...] = MODELES,
    vignettes: Vignettes | None = None,
    appel: Callable = client_ia.analyser,
    annee: int | None = None,
) -> list[Bilan]:
    if vignettes is None:
        from bitumap.sources import ortho

        cache: dict[tuple[float, float], list] = {}

        def vignettes(lon, lat):  # mêmes images pour tous les modèles
            if (lon, lat) not in cache:
                cache[(lon, lat)] = ortho.vignettes_historiques(lon, lat)
            return cache[(lon, lat)]

    annee = annee or date.today().year
    return [
        Bilan(m, [evaluer_point(p, m, vignettes, appel, annee) for p in echantillon])
        for m in modeles
    ]


def retenu(bilans: list[Bilan]) -> Bilan:
    """R7 : le plus exact (bonne période), puis le moins cher."""
    return min(bilans, key=lambda b: (-b.taux("bonne_periode"), b.cout_eur))


def rapport_markdown(bilans: list[Bilan]) -> str:
    choix = retenu(bilans)
    lignes = [
        f"# Évaluation des modèles vision — {date.today().isoformat()}",
        "",
        f"Échantillon : {bilans[0].n} points P1 à date de réfection connue (SC-012 : bonne"
        f" période ≥ {SEUIL_SC012:.0%}).",
        "",
        "| Modèle | Bonne période | Bonne classe d'effet | Non évalués | Coût total | Coût/point"
        " | Durée moyenne |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in bilans:
        duree = sum(m.duree_s for m in b.mesures) / b.n if b.n else 0
        lignes.append(
            f"| {b.modele}{' **(retenu)**' if b is choix else ''} | {b.taux('bonne_periode'):.0%}"
            f" | {b.taux('bonne_classe'):.0%} | {b.non_evalues} | {b.cout_eur:.4f} €"
            f" | {b.cout_eur / b.n if b.n else 0:.5f} € | {duree:.1f} s |"
        )
    atteint = choix.taux("bonne_periode") >= SEUIL_SC012
    lignes += [
        "",
        f"**Modèle retenu** : `{choix.modele}` (règle R7 : le plus exact, puis le moins cher)."
        f" SC-012 {'atteint' if atteint else '**non atteint**'}"
        f" ({choix.taux('bonne_periode'):.0%}).",
        "",
        f"Aucun changement de priorité dû à l'IA seule : effet borné ×{EFFET_5_12_ANS} à"
        f" ×{EFFET_PLUS_12_ANS}, appliqué après le figement des priorités et à l'intérieur des"
        " P1 seulement (tests/unit/test_score.py).",
        "",
        "## Détail par point",
        "",
        "| Point | Réfection réelle | " + " | ".join(b.modele for b in bilans) + " |",
        "|---|---|" + "---|" * len(bilans),
    ]
    for i, m0 in enumerate(bilans[0].mesures):
        cellules = []
        for b in bilans:
            m = b.mesures[i]
            if m.periode:
                cellules.append(f"{m.periode[0]}–{m.periode[1]} {'✓' if m.bonne_periode else '✗'}")
            else:
                cellules.append(m.erreur or m.statut)
        lignes.append(f"| {m0.point_id} | {m0.verite} | " + " | ".join(cellules) + " |")
    return "\n".join(lignes) + "\n"


def main(arguments: list[str] | None = None) -> int:
    analyse = argparse.ArgumentParser(description="Compare les modèles vision (SC-012).")
    analyse.add_argument("--echantillon", type=Path, required=True)
    analyse.add_argument("--modeles", nargs="+", default=list(MODELES))
    analyse.add_argument("--sortie", type=Path)
    args = analyse.parse_args(arguments)
    echantillon = json.loads(args.echantillon.read_text(encoding="utf-8"))["points"]
    bilans = evaluer(echantillon, tuple(args.modeles))
    texte = rapport_markdown(bilans)
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
