"""Évaluation de la méthode 2.0 sur les relevés de terrain (004 T039, R7, FR-006, FR-013).

Usage :
  uv run python -m bitumap.methode.evaluer --releves releves-92026.geojson … \
      --communes 92026 92004 92012 [--soleil soleil.csv] [--sortie evaluation-v2.md]

Entrées : exports des relevés de 003 (``/terrain/{insee}/releves.geojson`` ou ``.csv``) ;
communes de référence (au moins 3) ; facultatif, heures de soleil observées (CSV
``point;heures``, SC-002). Refus explicite sous ``MIN_POINTS`` points relevés ou
``MIN_COMMUNES`` communes. Orniéré = constat « marqué » ou « grave » (dernier relevé du point).

Chaque commune est calculée en 1.2, en 2.0 (indicateurs de chaleur retenus par la méthode),
puis en 2.0 avec chaque candidat de chaleur retenu seul (FR-006). L'âge de l'enrobé n'est pas
évalué (aucun appel d'IA) : il ne change jamais la priorité, donc aucune mesure ci-dessous.

Sortie Markdown aux sections du contrat 004 § 2 ; la recommandation est à confirmer par le
mainteneur. Sources en ligne (comme le lot) : lancé par le mainteneur, jamais en CI.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bitumap.facteurs import chaleur
from bitumap.modele import Point
from bitumap.score import comparaison
from bitumap.score.methode import (
    INDICATEURS_CHALEUR_RETENUS,
    LIBELLES_GROUPES,
    VERSION_METHODE,
    VERSION_METHODE_V2,
)

MIN_POINTS = 100
MIN_COMMUNES = 3
ORNIERES = ("marque", "grave")
PRIORITAIRES = ("P1a", "P1b", "P1c")
OBJECTIF_SC001_POINTS = 10.0
SEUIL_INDICATEUR_POINTS = 2.0
OBJECTIF_SC002_H = 1.5
# Libellés de l'export de 003 (``terrain.depot.LIBELLES_NIVEAUX``) → codes.
NIVEAUX = {"absent": "absent", "léger": "leger", "marqué": "marque", "grave": "grave"}

# calcul(insee, méthode, indicateurs retenus) → points classés de la commune.
Calcul = Callable[[str, str, frozenset[str]], list[Point]]


class RefusEvaluation(Exception):
    """Référence insuffisante (FR-013) : l'évaluation n'est pas produite."""


@dataclass
class Releve:
    point: str
    niveau: str
    date: str

    @property
    def orniere(self) -> bool:
        return self.niveau in ORNIERES


def _niveau(texte: str) -> str:
    texte = (texte or "").strip().lower()
    if texte not in NIVEAUX and texte not in NIVEAUX.values():
        raise ValueError(f"niveau constaté inconnu : {texte!r}")
    return NIVEAUX.get(texte, texte)


def lire_releves(chemins: list[Path]) -> dict[str, Releve]:
    """Dernier relevé de chaque point, depuis des exports GeoJSON ou CSV de 003."""
    releves: list[Releve] = []
    for chemin in chemins:
        texte = chemin.read_text(encoding="utf-8-sig")
        if chemin.suffix.lower() in (".geojson", ".json"):
            lignes = [e["properties"] for e in json.loads(texte)["features"]]
        else:
            lignes = list(csv.DictReader(io.StringIO(texte), delimiter=";"))
        releves += [
            Releve(str(ligne["point"]), _niveau(ligne["niveau_constate"]), str(ligne["date"]))
            for ligne in lignes
        ]
    derniers: dict[str, Releve] = {}
    for r in sorted(releves, key=lambda r: (r.point, r.date)):
        derniers[r.point] = r
    return derniers


def lire_soleil(chemin: Path | None) -> dict[str, float]:
    """Heures de soleil observées par point (CSV ``point;heures``), SC-002."""
    if chemin is None:
        return {}
    lignes = csv.DictReader(io.StringIO(chemin.read_text(encoding="utf-8-sig")), delimiter=";")
    return {str(ligne["point"]): float(ligne["heures"].replace(",", ".")) for ligne in lignes}


def part_prioritaires(points: list[Point], releves: dict[str, Releve]) -> float | None:
    """Part (%) des points orniérés relevés classés Critique, Sérieux ou Important."""
    ornieres = [p for p in points if (r := releves.get(p.id)) is not None and r.orniere]
    if not ornieres:
        return None
    return 100 * sum(p.groupe in PRIORITAIRES for p in ornieres) / len(ornieres)


@dataclass
class Commune:
    insee: str
    v1: list[Point]
    v2: list[Point]
    candidats: dict[str, list[Point]] = field(default_factory=dict)


@dataclass
class Evaluation:
    communes: list[Commune]
    releves: dict[str, Releve]
    soleil: dict[str, float]

    def _tous(self, choix: Callable[[Commune], list[Point]]) -> list[Point]:
        return [p for c in self.communes for p in choix(c)]

    def releves_de(self, c: Commune) -> list[Releve]:
        ids = {p.id for p in c.v2}
        return [r for pid, r in self.releves.items() if pid in ids]

    def sc001(self) -> tuple[float | None, float | None]:
        return (
            part_prioritaires(self._tous(lambda c: c.v1), self.releves),
            part_prioritaires(self._tous(lambda c: c.v2), self.releves),
        )

    def indicateur(self, nom: str) -> dict:
        """Mesure avec et sans l'indicateur, globale et par commune ; décision (FR-006)."""
        sans = part_prioritaires(self._tous(lambda c: c.v2), self.releves)
        avec = part_prioritaires(self._tous(lambda c: c.candidats[nom]), self.releves)
        par_commune = {}
        for c in self.communes:
            s = part_prioritaires(c.v2, self.releves)
            a = part_prioritaires(c.candidats[nom], self.releves)
            par_commune[c.insee] = None if None in (s, a) else a - s
        ecart = None if None in (sans, avec) else avec - sans
        degradees = [i for i, e in par_commune.items() if e is not None and e < 0]
        retenu = ecart is not None and ecart >= SEUIL_INDICATEUR_POINTS and not degradees
        if ecart is None:
            raison = "aucun point orniéré relevé"
        elif degradees:
            raison = "dégrade la mesure à " + ", ".join(degradees)
        elif ecart < SEUIL_INDICATEUR_POINTS:
            raison = f"apport inférieur à {SEUIL_INDICATEUR_POINTS:.0f} points"
        else:
            raison = "améliore la mesure sans dégrader aucune commune"
        return {
            "sans": sans,
            "avec": avec,
            "ecart": ecart,
            "par_commune": par_commune,
            "retenu": retenu,
            "raison": raison,
        }

    def sc002(self) -> tuple[int, float | None]:
        ecarts = []
        for p in self._tous(lambda c: c.v2):
            observe = self.soleil.get(p.id)
            f = p.facteur("ensoleillement")
            if observe is not None and f is not None and f.valeur is not None:
                ecarts.append(abs(float(f.valeur) - observe))
        return len(ecarts), (sum(ecarts) / len(ecarts) if ecarts else None)


def verifier_reference(releves: dict[str, Releve], points_par_commune: dict[str, set[str]]):
    """Refus explicite si la référence est insuffisante (FR-013)."""
    par_commune = {
        insee: sum(pid in ids for pid in releves) for insee, ids in points_par_commune.items()
    }
    total = sum(par_commune.values())
    avec_releves = [i for i, n in par_commune.items() if n]
    if total < MIN_POINTS or len(avec_releves) < MIN_COMMUNES:
        raise RefusEvaluation(
            f"Référence insuffisante : {total} points relevés dans {len(avec_releves)} "
            f"commune(s) ; il en faut au moins {MIN_POINTS} dans {MIN_COMMUNES} communes."
        )


def evaluer(
    communes: list[str], releves: dict[str, Releve], soleil: dict[str, float], calcul: Calcul
) -> Evaluation:
    resultat = []
    for insee in communes:
        v2 = calcul(insee, VERSION_METHODE_V2, INDICATEURS_CHALEUR_RETENUS)
        resultat.append(Commune(insee, calcul(insee, VERSION_METHODE, frozenset()), v2))
    verifier_reference(releves, {c.insee: {p.id for p in c.v2} for c in resultat})
    for c in resultat:
        for nom in chaleur.CANDIDATS:
            c.candidats[nom] = calcul(c.insee, VERSION_METHODE_V2, frozenset({nom}))
    return Evaluation(resultat, releves, soleil)


def _pct(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:.1f} %".replace(".", ",")


def _pts(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:+.1f} points".replace(".", ",")


def rapport_markdown(e: Evaluation) -> str:
    v1, v2 = e.sc001()
    ecart = None if None in (v1, v2) else v2 - v1
    lignes = [
        f"# Évaluation de la méthode {VERSION_METHODE_V2} — {date.today().isoformat()}",
        "",
        "## Référence",
        "",
        "| Commune | Points relevés | Orniérés (marqué ou grave) |",
        "|---|---|---|",
    ]
    for c in e.communes:
        rs = e.releves_de(c)
        lignes.append(f"| {c.insee} | {len(rs)} | {sum(r.orniere for r in rs)} |")
    lignes += [
        "",
        "## SC-001",
        "",
        "Part des points orniérés classés Critique, Sérieux ou Important (objectif : "
        f"+{OBJECTIF_SC001_POINTS:.0f} points ou plus).",
        "",
        f"- Méthode {VERSION_METHODE} : {_pct(v1)}",
        f"- Méthode {VERSION_METHODE_V2} : {_pct(v2)}",
        f"- Écart : {_pts(ecart)} — "
        + (
            "**atteint**"
            if ecart is not None and ecart >= OBJECTIF_SC001_POINTS
            else "**non atteint**"
        ),
        "",
        "## Indicateurs",
        "",
        f"Un indicateur est retenu s'il améliore la mesure d'au moins {SEUIL_INDICATEUR_POINTS:.0f}"
        " points et ne la dégrade dans aucune commune (FR-006).",
        "",
        "| Indicateur | Sans | Avec | Écart | "
        + " | ".join(c.insee for c in e.communes)
        + " | Décision | Raison |",
        "|---|---|---|---|" + "---|" * len(e.communes) + "---|---|",
    ]
    for nom in chaleur.CANDIDATS:
        m = e.indicateur(nom)
        lignes.append(
            f"| {nom} | {_pct(m['sans'])} | {_pct(m['avec'])} | {_pts(m['ecart'])} | "
            + " | ".join(_pts(m["par_commune"][c.insee]) for c in e.communes)
            + f" | {'retenu' if m['retenu'] else 'écarté'} | {m['raison']} |"
        )
    n_soleil, ecart_soleil = e.sc002()
    lignes += [
        "",
        "## Ensoleillement (SC-002)",
        "",
        f"Points observés : {n_soleil} ; écart moyen calculé / observé : "
        + ("non mesuré" if ecart_soleil is None else f"{ecart_soleil:.2f} h".replace(".", ","))
        + f" (objectif : moins de {OBJECTIF_SC002_H:.1f} h sur 30 points).".replace(".", ",", 1),
        "",
        "## Changements de niveau",
        "",
    ]
    groupes = comparaison.GROUPES
    for c in e.communes:
        bilan = comparaison.comparer(c.v1, c.v2)
        lignes += [
            f"### {c.insee}",
            "",
            f"| {VERSION_METHODE} \\ {VERSION_METHODE_V2} | "
            + " | ".join(LIBELLES_GROUPES[g] for g in groupes)
            + " |",
            "|---|" + "---|" * len(groupes),
        ]
        for g1 in groupes:
            lignes.append(
                f"| {LIBELLES_GROUPES[g1]} | "
                + " | ".join(str(bilan[g1][g2]) for g2 in groupes)
                + " |"
            )
        lignes.append("")
    retenus = [n for n in chaleur.CANDIDATS if e.indicateur(n)["retenu"]]
    sc001_ok = ecart is not None and ecart >= OBJECTIF_SC001_POINTS
    sc002_ok = ecart_soleil is not None and n_soleil >= 30 and ecart_soleil < OBJECTIF_SC002_H
    lignes += [
        "## Décision",
        "",
        "Recommandation (**à confirmer par le mainteneur**) : "
        + (
            "mise en service de la méthode 2.0"
            if sc001_ok and sc002_ok
            else "pas de mise en service en l'état"
        )
        + f" ; SC-001 {'atteint' if sc001_ok else 'non atteint'}, "
        f"SC-002 {'atteint' if sc002_ok else 'non atteint ou non mesuré'}.",
        "",
        "Indicateurs de chaleur à inscrire dans `INDICATEURS_CHALEUR_RETENUS` : "
        + (", ".join(f"`{n}`" for n in retenus) if retenus else "aucun")
        + ".",
        "",
    ]
    return "\n".join(lignes)


def calcul_en_ligne(dossier_cache: Path) -> Calcul:
    """Calcul réel (sources en ligne, comme le lot), sans IA."""
    from bitumap.calcul import calculer_commune
    from bitumap.lot import regional
    from bitumap.sources.fournisseur import FournisseurEnLigne
    from bitumap.territoire.api_geo import commune_par_insee

    donnees = regional.preparer(dossier_cache)
    memoires: dict[str, comparaison.Memoire] = {}

    def calcul(insee: str, methode: str, retenus: frozenset[str]) -> list[Point]:
        if insee not in memoires:  # une lecture des sources par commune
            memoires[insee] = comparaison.Memoire(
                FournisseurEnLigne(insee, donnees.osm_gpkg, donnees.osm_date)
            )
        nom = commune_par_insee(insee).nom
        return calculer_commune(memoires[insee], nom, methode=methode, retenus=retenus).points

    return calcul


def main(arguments: list[str] | None = None, calcul: Calcul | None = None) -> int:
    analyse = argparse.ArgumentParser(description="Évalue la méthode 2.0 sur les relevés (R7).")
    analyse.add_argument("--releves", type=Path, nargs="+", required=True)
    analyse.add_argument("--communes", nargs="+", required=True)
    analyse.add_argument("--soleil", type=Path)
    analyse.add_argument("--sortie", type=Path)
    analyse.add_argument("--cache", type=Path, default=Path("var/cache"))
    args = analyse.parse_args(arguments)
    if len(args.communes) < MIN_COMMUNES:
        print(f"Il faut au moins {MIN_COMMUNES} communes de référence.", file=sys.stderr)
        return 2
    try:
        evaluation = evaluer(
            args.communes,
            lire_releves(args.releves),
            lire_soleil(args.soleil),
            calcul or calcul_en_ligne(args.cache),
        )
    except RefusEvaluation as refus:
        print(refus, file=sys.stderr)
        return 2
    texte = rapport_markdown(evaluation)
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
