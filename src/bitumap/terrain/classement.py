"""Classement corrigé par le terrain : réfection confirmée (004 R9, FR-016 à FR-018).

Couche **distincte**, calculée par l'API au moment où elle sert un rapport 2.0 : le score
estimé, ``points.geojson`` et l'empreinte du rapport ne changent jamais (principe VI).

- **Réfection confirmée** (FR-016) : plus récente année de réfection d'un relevé visible du
  point, de source « constatée » ou « services techniques » ; « estimée par l'agent » n'a pas
  d'effet.
- **Effet** (FR-017) : ``min(1,0 ; 0,5 + 0,05 × n)``, ``n`` = été de référence du rapport −
  année de réfection (≥ 0) : même rapport, mêmes relevés ⇒ même classement corrigé, quel que
  soit le jour de consultation.
- **Annulation** (FR-018) : le relevé visible le plus récent du point, daté d'une année ≥
  l'année de réfection, constate un orniérage « marqué » ou « grave ».
- Rangs et niveaux corrigés : mêmes règles que le score estimé (``score.combinaison``) ; la
  réfection agit avant le figement des priorités, l'âge de l'enrobé après, comme dans le job.

Aucune donnée personnelle dans le résultat (ni auteur, ni adresse, ni photo).
"""

from __future__ import annotations

from datetime import datetime

from bitumap.db import connexion
from bitumap.modele import Facteur, Point
from bitumap.score import combinaison
from bitumap.terrain import depot

SOURCES_CONFIRMEES = ("constatee", "services_techniques")
ORNIERES = ("marque", "grave")
EFFET_ANNEE_TRAVAUX = 0.5
REPRISE_PAR_AN = 0.05
FACTEUR = "refection_confirmee"
MOTIF_ANNULATION = "réfection sans effet : orniérage constaté après les travaux"


def effet(ete_reference: int, annee_refection: int) -> float:
    n = max(0, ete_reference - annee_refection)
    return round(min(1.0, EFFET_ANNEE_TRAVAUX + REPRISE_PAR_AN * n), 4)


def _annee(date) -> int:
    return (date if isinstance(date, datetime) else datetime.fromisoformat(str(date))).year


def refections_depuis(releves: list[dict]) -> dict[str, dict]:
    """Par point : réfection confirmée la plus récente et dernier relevé visible.

    ``releves`` : relevés visibles (dernière version) avec ``point_id``, ``cree_le``,
    ``niveau``, ``annee_refection``, ``source_refection``, dans n'importe quel ordre."""
    resultat: dict[str, dict] = {}
    for r in sorted(releves, key=lambda r: (r["point_id"], str(r["cree_le"]))):
        point = resultat.setdefault(r["point_id"], {"annee_refection": None})
        point["dernier_niveau"], point["dernier_annee"] = r["niveau"], _annee(r["cree_le"])
        annee, source = r.get("annee_refection"), r.get("source_refection")
        if (
            annee is not None
            and source in SOURCES_CONFIRMEES
            and (point["annee_refection"] is None or annee > point["annee_refection"])
        ):
            point["annee_refection"], point["source_refection"] = annee, source
    return {pid: p for pid, p in resultat.items() if p["annee_refection"] is not None}


def refections(commune_insee: str) -> dict[str, dict]:
    """Réfections confirmées des points de la commune, depuis les relevés visibles (003)."""
    with connexion() as conn:
        lignes = depot.releves_de_la_commune(conn, commune_insee)
    return refections_depuis(lignes)


def _point(feature: dict) -> Point:
    pr = feature["properties"]
    lon, lat = feature["geometry"]["coordinates"]
    p = Point(pr["id"], pr["type"], pr["nom"], lon, lat)
    p.facteurs = [Facteur(f["nom"], f.get("valeur"), float(f["effet"])) for f in pr["facteurs"]]
    return p


def corriger(points_geojson: dict, refections_: dict[str, dict], ete_reference: int) -> dict:
    """Bloc ``classement-terrain`` d'un rapport 2.0 (data-model 004)."""
    points = [_point(f) for f in points_geojson["features"]]
    corriges: dict[str, dict] = {}
    for p in points:
        r = refections_.get(p.id)
        if r is None:
            continue
        annule = r["dernier_niveau"] in ORNIERES and r["dernier_annee"] >= r["annee_refection"]
        e = 1.0 if annule else effet(ete_reference, r["annee_refection"])
        corriges[p.id] = {
            "annee_refection": r["annee_refection"],
            "source_refection": r["source_refection"],
            "effet": e,
            "annule": annule,
            "motif": MOTIF_ANNULATION if annule else None,
        }
        # Agit avant le figement des priorités (contrairement à l'âge de l'enrobé).
        p.facteurs.append(Facteur(FACTEUR, r["annee_refection"], e))
    classes = combinaison.finaliser(combinaison.prioriser(points))
    for p in classes:
        if p.id in corriges:
            corriges[p.id] |= {"rang": p.rang, "groupe": p.groupe}
    return {
        "points": corriges,
        "nb_points_corriges": sum(c["effet"] < 1.0 for c in corriges.values()),
        "classement": [{"id": p.id, "rang": p.rang, "groupe": p.groupe} for p in classes],
    }
