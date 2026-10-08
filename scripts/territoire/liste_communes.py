#!/usr/bin/env python3
"""Génère la liste intégrée des communes d'Île-de-France (008, research R1).

Source : API Géo (geo.api.gouv.fr), Licence Ouverte 2.0. Lancé à la main, au plus une fois
par an (le référentiel change au 1er janvier) ; le fichier produit est relu dans une PR.

Usage : ``uv run python scripts/territoire/liste_communes.py``

Codes retour : 0 fichier écrit, 1 réponse incohérente (rien n'est écrit).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import httpx

from bitumap.territoire.api_geo import DEPARTEMENTS_IDF, URL_API_GEO, USER_AGENT

SORTIE = Path(__file__).resolve().parents[2] / "src/bitumap/territoire/communes_idf.json"
CHAMPS = "nom,code,codeDepartement"
PARIS = "75056"  # Paris entier : un rapport porte sur un arrondissement (LL-027)
MINIMUM = 1200


def _lire(client: httpx.Client, **params: str) -> list[dict]:
    reponse = client.get("/communes", params={"codeRegion": "11", "fields": CHAMPS, **params})
    reponse.raise_for_status()
    return reponse.json()


def main() -> int:
    with httpx.Client(base_url=URL_API_GEO, timeout=30, headers={"User-Agent": USER_AGENT}) as c:
        communes = _lire(c)
        arrondissements = _lire(c, type="arrondissement-municipal")
    entrees = sorted(
        {
            (x["code"], x["nom"], x["codeDepartement"])
            for x in communes + arrondissements
            if x["code"] != PARIS
        }
    )
    hors_idf = [e for e in entrees if e[2] not in DEPARTEMENTS_IDF]
    nb_arrondissements = sum(1 for e in entrees if e[0].startswith("751"))
    if len(entrees) < MINIMUM or hors_idf or nb_arrondissements != 20:
        print(
            f"Liste refusée : {len(entrees)} entrées, {nb_arrondissements} arrondissements, "
            f"{len(hors_idf)} hors Île-de-France.",
            file=sys.stderr,
        )
        return 1
    lignes = ",\n".join("  " + json.dumps(list(e), ensure_ascii=False) for e in entrees)
    entete = {
        "source": "API Géo (geo.api.gouv.fr), Licence Ouverte 2.0",
        "url": f"{URL_API_GEO}/communes?codeRegion=11&fields={CHAMPS}",
        "genere_le": dt.date.today().isoformat(),
    }
    texte = json.dumps(entete, ensure_ascii=False, indent=1)[:-2]
    SORTIE.write_text(f'{texte},\n "communes": [\n{lignes}\n ]\n}}\n', encoding="utf-8")
    print(f"{SORTIE.name} : {len(entrees)} entrées, dont {nb_arrondissements} arrondissements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
