"""Recherche d'une commune d'Île-de-France par son nom, sur la liste intégrée (008, R1 à R3).

Aucun appel réseau : la liste ``communes_idf.json`` est générée par
``scripts/territoire/liste_communes.py`` et versionnée avec le code.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from importlib import resources

from bitumap.territoire.api_geo import Commune

LONGUEUR_MAX = 100
SEUIL = 3  # FR-016 : propositions dès la 3e lettre ; en dessous, nom exact seulement
_SEPARATEURS = re.compile(r"[\s\-'’]+")
_SAINT = re.compile(r"\b(st|ste)\b")
_ARRONDISSEMENT = re.compile(r"^Paris (\d+)(er|e) Arrondissement$")


@dataclass(frozen=True)
class _Entree:
    commune: Commune
    formes: tuple[str, ...]  # nom normalisé, puis alias (arrondissements)


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation ramenée à des espaces, « st » ⇒ « saint »."""
    decompose = unicodedata.normalize("NFKD", texte[:LONGUEUR_MAX])
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    forme = _SEPARATEURS.sub(" ", sans_accents.lower()).strip()
    return _SAINT.sub(lambda m: "saint" if m.group(1) == "st" else "sainte", forme)


def _alias(nom: str) -> tuple[str, ...]:
    m = _ARRONDISSEMENT.match(nom)
    if not m:
        return ()
    numero, suffixe = m.groups()
    return (f"paris {numero}", f"paris {numero}{suffixe}", f"{numero}{suffixe}")


@cache
def _fichier() -> dict:
    texte = resources.files("bitumap.territoire").joinpath("communes_idf.json").read_text("utf-8")
    return json.loads(texte)


@cache
def _entrees() -> tuple[_Entree, ...]:
    return tuple(
        _Entree(Commune(insee, nom, dep), (normaliser(nom), *_alias(nom)))
        for insee, nom, dep in _fichier()["communes"]
    )


@cache
def _par_insee() -> dict[str, Commune]:
    return {e.commune.insee: e.commune for e in _entrees()}


def metadonnees() -> dict[str, str]:
    """Source, licence et date de la liste (principe III)."""
    return {k: v for k, v in _fichier().items() if k != "communes"}


def par_insee(insee: str) -> Commune | None:
    return _par_insee().get(insee)


def _rang(formes: tuple[str, ...], q: str) -> int | None:
    """0 nom exact, 1 début du nom, 2 début d'un mot, 3 contenu ; ``None`` sinon."""
    meilleur = None
    compacte = q.replace(" ", "")
    for forme in formes:
        sans_espace = forme.replace(" ", "")
        if forme == q or sans_espace == compacte:
            rang = 0
        elif forme.startswith(q) or sans_espace.startswith(compacte):  # « lhay » ⇒ L'Haÿ
            rang = 1
        elif f" {q}" in f" {forme}":
            rang = 2
        elif q in forme:
            rang = 3
        else:
            continue
        meilleur = rang if meilleur is None else min(meilleur, rang)
    return meilleur


def rechercher(saisie: str, limite: int = 10) -> list[Commune]:
    """Communes dont le nom correspond à ``saisie``, les plus pertinentes en premier."""
    if len(saisie) > LONGUEUR_MAX:
        return []
    q = normaliser(saisie)
    if not q:
        return []
    trouvees = []
    for entree in _entrees():
        rang = _rang(entree.formes, q)
        if rang is None or (len(q) < SEUIL and rang != 0):
            continue
        trouvees.append((rang, entree.formes[0], entree.commune.departement, entree.commune))
    trouvees.sort(key=lambda t: t[:3])
    return [t[3] for t in trouvees[:limite]]
