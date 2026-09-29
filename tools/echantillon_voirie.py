"""Échantillon de points pour vérifier le type de route à la main (T068, SC-005 : ≥ 90 %).

Tire 50 points au hasard (graine fixe, donc reproductible) et écrit un CSV à compléter :
colonne ``exact`` (o/n) après contrôle sur Géoportail ou le terrain, ``remarque`` libre.

Usage :
  uv run python tools/echantillon_voirie.py rapport/points.geojson > echantillon.csv
  uv run python tools/echantillon_voirie.py --fixtures tests/fixtures/courbevoie 92026 Courbevoie
Options : --taille N (50), --graine G (2026).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

COLONNES = [
    "id",
    "nom",
    "voie",
    "classement",
    "gestionnaire",
    "numero",
    "statut",
    "lien_geoportail",
    "exact",
    "remarque",
]


def _points_geojson(chemin: Path) -> list[dict]:
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    points = []
    for f in donnees["features"]:
        p = dict(f["properties"])
        p["lon"], p["lat"] = f["geometry"]["coordinates"][:2]
        points.append(p)
    return points


def _points_fixtures(dossier: Path, insee: str, nom: str) -> list[dict]:
    from bitumap.calcul import calculer_commune
    from bitumap.sources.fournisseur import FournisseurFige

    resultat = calculer_commune(FournisseurFige(dossier, insee), nom)
    return [p.en_dict() for p in resultat.points]


def echantillon(points: list[dict], taille: int = 50, graine: int = 2026) -> list[dict]:
    """Tirage sans remise, stable pour une même liste de points et une même graine."""
    tries = sorted(points, key=lambda p: p["id"])
    return random.Random(graine).sample(tries, min(taille, len(tries)))  # noqa: S311 (non crypto)


def ligne(p: dict) -> dict:
    route = p["route"]
    lien = f"https://www.geoportail.gouv.fr/carte?c={p['lon']:.6f},{p['lat']:.6f}&z=19"
    return {
        "id": p["id"],
        "nom": p["nom"],
        "voie": p.get("voie", ""),
        "classement": route["classement"],
        "gestionnaire": route.get("gestionnaire") or "",
        "numero": route.get("numero") or "",
        "statut": route["statut"],
        "lien_geoportail": lien,
        "exact": "",
        "remarque": "",
    }


def main(arguments: list[str] | None = None) -> int:
    analyse = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyse.add_argument("source", nargs="?", type=Path, help="points.geojson d'un rapport")
    analyse.add_argument("--fixtures", nargs=3, metavar=("DOSSIER", "INSEE", "NOM"))
    analyse.add_argument("--taille", type=int, default=50)
    analyse.add_argument("--graine", type=int, default=2026)
    args = analyse.parse_args(arguments)
    if args.fixtures:
        dossier, insee, nom = args.fixtures
        points = _points_fixtures(Path(dossier), insee, nom)
    elif args.source:
        points = _points_geojson(args.source)
    else:
        analyse.error("indiquer un points.geojson ou --fixtures")
    ecrivain = csv.DictWriter(sys.stdout, fieldnames=COLONNES)
    ecrivain.writeheader()
    for p in echantillon(points, args.taille, args.graine):
        ecrivain.writerow(ligne(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
