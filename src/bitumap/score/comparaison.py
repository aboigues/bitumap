"""Comparaison 1.2 / 2.0 d'une commune (004 US4, R6, FR-011, SC-004).

Dans le même lot, la commune est aussi calculée en méthode 1.2 :

- **mêmes sources** : les réponses du fournisseur lues pour la 2.0 sont gardées en mémoire et
  resservies (aucun accès réseau de plus) ;
- **aucun appel d'IA supplémentaire** : l'âge de l'enrobé des points analysés en 2.0 est
  repris tel quel ; un point P1 en 1.2 seulement reste « non évalué » (l'âge ne change jamais
  la priorité, seulement l'ordre et les sous-groupes à l'intérieur du P1, principe V).

Chaque point 2.0 reçoit ``niveau_v1`` (son groupe en 1.2) et, si le niveau a changé,
``raison_changement`` : le facteur dont l'effet a le plus varié en logarithme. Les
indicateurs de chaleur de la 2.0 sont regroupés et comparés à l'aléa de la 1.2. Si aucun
facteur du point n'a bougé, le changement vient du déplacement des autres points (rangs
relatifs).
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable

from bitumap.calcul import ResultatCommune, calculer_commune
from bitumap.modele import Facteur, Point
from bitumap.score import combinaison
from bitumap.score.methode import LIBELLES_GROUPES, VERSION_METHODE

GROUPES = ("P1a", "P1b", "P1c", "P2", "P3")
# Variation d'effet en dessous de laquelle un facteur est considéré inchangé (0,5 %).
VARIATION_MIN = math.log(1.005)
RAISON_AUTRES_POINTS = "déplacement des autres points (classement relatif)"

LIBELLES_FACTEURS = {
    "charge": "passages de bus",
    "type": "type de point",
    "arret_pres_feu": "arrêt près d'un feu",
    "pointe": "bus en pointe",
    "pente": "pente",
    "revetement": "revêtement",
    "ouvrage_art": "ouvrage d'art",
    "ensoleillement": "ensoleillement",
    "chaleur": "chaleur",
    "poids_lourds": "poids lourds",
    combinaison.FACTEUR_IA: "âge de l'enrobé",
}


class Memoire:
    """Enveloppe d'un fournisseur : chaque réponse est lue une fois, puis resservie."""

    def __init__(self, cible):
        self._cible = cible
        self._reponses: dict[str, object] = {}

    def __getattr__(self, nom):
        attribut = getattr(self._cible, nom)
        if not callable(attribut):
            return attribut

        def appel(*args, **kwargs):
            cle = f"{nom}:{args!r}:{sorted(kwargs.items())!r}"
            if cle not in self._reponses:
                self._reponses[cle] = attribut(*args, **kwargs)
            return copy.deepcopy(self._reponses[cle])

        return appel


def reprise_ia(points_v2: list[Point]) -> Callable[[list[Point]], None]:
    """Analyse IA de la 1.2 : reprend l'âge de l'enrobé déjà évalué en 2.0, sans appel."""
    ages = {p.id: f for p in points_v2 if (f := p.facteur(combinaison.FACTEUR_IA)) is not None}

    def analyser(p1: list[Point]) -> None:
        for p in p1:
            age = ages.get(p.id)
            p.facteurs.append(
                copy.deepcopy(age)
                if age is not None
                else Facteur(
                    combinaison.FACTEUR_IA,
                    None,
                    1.0,
                    provenance="ia",
                    statut="non_evalue",
                    explication="Âge de l'enrobé non évalué",
                )
            )

    return analyser


def _famille(nom: str) -> str:
    return "chaleur" if nom.startswith("chaleur") else nom


def _effets(point: Point) -> dict[str, float]:
    """Effet de chaque famille de facteurs (produit des effets de la famille)."""
    effets: dict[str, float] = {}
    for f in point.facteurs:
        famille = _famille(f.nom)
        effets[famille] = effets.get(famille, 1.0) * f.effet
    return effets


def _effet_texte(effet: float) -> str:
    return f"×{effet:.2f}".replace(".", ",")


def raison(v1: Point, v2: Point) -> str:
    """Facteur dont l'effet a le plus varié entre 1.2 et 2.0 (R6)."""
    e1, e2 = _effets(v1), _effets(v2)
    variations = sorted(
        ((abs(math.log(e2.get(n, 1.0)) - math.log(e1.get(n, 1.0))), n) for n in set(e1) | set(e2)),
        key=lambda vn: (-vn[0], vn[1]),
    )
    if not variations or variations[0][0] < VARIATION_MIN:
        return RAISON_AUTRES_POINTS
    nom = variations[0][1]
    libelle = LIBELLES_FACTEURS.get(nom, nom.replace("_", " "))
    avant, apres = e1.get(nom, 1.0), e2.get(nom, 1.0)
    return f"{libelle} ({_effet_texte(avant)} en v1, {_effet_texte(apres)} en v2)"


def comparer(points_v1: list[Point], points_v2: list[Point]) -> dict[str, dict[str, int]]:
    """Renseigne ``niveau_v1`` et ``raison_changement`` des points 2.0 ; renvoie le bilan
    (nombre de points par niveau v1, puis niveau v2)."""
    par_id = {p.id: p for p in points_v1}
    bilan = {g1: dict.fromkeys(GROUPES, 0) for g1 in GROUPES}
    for p in points_v2:
        ancien = par_id.get(p.id)
        if ancien is None:
            continue
        p.niveau_v1 = ancien.groupe
        p.raison_changement = raison(ancien, p) if ancien.groupe != p.groupe else None
        bilan[ancien.groupe][p.groupe] += 1
    return bilan


def libelle_changement(p: Point) -> str | None:
    """« v1 : Sérieux — raison : chaleur (…) », ou ``None`` si le niveau n'a pas changé."""
    if p.niveau_v1 is None or p.raison_changement is None:
        return None
    return f"v1 : {LIBELLES_GROUPES[p.niveau_v1]} — raison : {p.raison_changement}"


def calculer_avec_v1(
    f, nom_commune: str, analyse_ia: Callable[[list[Point]], None] | None = None
) -> ResultatCommune:
    """Calcul 2.0 de la commune, puis 1.2 sur les mêmes sources et réponses d'IA ; le
    résultat 2.0 porte ``niveau_v1``, ``raison_changement`` et ``bilan_changements``."""
    memoire = Memoire(f)
    resultat = calculer_commune(memoire, nom_commune, analyse_ia)
    v1 = calculer_commune(
        memoire, nom_commune, reprise_ia(resultat.points), methode=VERSION_METHODE
    )
    resultat.bilan_changements = comparer(v1.points, resultat.points)
    return resultat
