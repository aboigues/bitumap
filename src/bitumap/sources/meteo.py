"""Données quotidiennes de Météo-France, méthode 2.0 (004 R4, US2 ; partagées avec 007).

Jeu « Données climatologiques de base quotidiennes » (data.gouv.fr, Licence Ouverte 2.0) :
un fichier par département et par période, sans compte, hébergé en France. Le fichier est
choisi dans la liste des ressources du jeu (département de la station, période qui contient
l'été), sans nom de fichier écrit en dur.

L'été (juin à août) de la station sert d'**été de référence** affiché dans le rapport :
jours de forte chaleur (``SEUIL_FORTE_CHALEUR_C`` ou plus), maximum. Il n'est **jamais un
facteur de classement** : identique pour tous les points d'une commune, il ne change aucun
rang (R4).
"""

from __future__ import annotations

import csv
import gzip
import io
import re
from datetime import date

import httpx

from bitumap.sources.base import Provenance, SourceIndisponible, obtenir

JEU = "donnees-climatologiques-de-base-quotidiennes"
URL_JEU = f"https://www.data.gouv.fr/api/1/datasets/{JEU}/"
PAGE = f"https://www.data.gouv.fr/datasets/{JEU}"
LICENCE = "Licence Ouverte 2.0 (Météo-France)"
SEUIL_FORTE_CHALEUR_C = 30.0
SEUIL_TRES_FORTE_CHALEUR_C = 35.0
MOIS_ETE = (6, 7, 8)


def provenance(station: str, nom: str, ete: int) -> Provenance:
    return Provenance(
        f"Météo-France : données quotidiennes, station {nom} ({station}), été {ete}",
        LICENCE,
        PAGE,
        date.today(),
        "regionale",
    )


def nom_station(p: Provenance) -> str | None:
    """Nom usuel de la station, lu dans la provenance (« station NOM (code) »)."""
    trouve = re.search(r"station (.+) \(\d+\)", p.nom)
    return trouve.group(1) if trouve else None


def fichier(station: str, ete: int, client: httpx.Client) -> str:
    """URL du fichier quotidien (températures) du département de la station couvrant l'été."""
    departement = station[:2]
    ressources = obtenir(client, "Météo-France", URL_JEU).json().get("resources", [])
    for r in ressources:
        url = str(r.get("url", ""))
        if f"/Q_{departement}_" not in url or "RR-T-Vent" not in url:
            continue
        periode = re.search(r"(\d{4})-(\d{4})", url)
        if periode and int(periode.group(1)) <= ete <= int(periode.group(2)):
            return url
    raise SourceIndisponible("Météo-France", f"aucun fichier pour {departement}, été {ete}")


def _nombre(valeur: str) -> float | None:
    try:
        return float(valeur.replace(",", "."))
    except AttributeError, ValueError:
        return None


def lire_ete(contenu: bytes, station: str, ete: int) -> tuple[str, list[dict]]:
    """Nom de la station et jours de juin à août : ``{"date", "tx"}`` (°C, ``None`` si
    manquant), triés par date."""
    texte = gzip.decompress(contenu).decode("utf-8")
    nom, jours = station, []
    for ligne in csv.DictReader(io.StringIO(texte), delimiter=";"):
        if ligne["NUM_POSTE"] != station:
            continue
        jour = ligne["AAAAMMJJ"]
        if int(jour[:4]) != ete or int(jour[4:6]) not in MOIS_ETE:
            continue
        nom = ligne.get("NOM_USUEL") or station
        jours.append({"date": f"{jour[:4]}-{jour[4:6]}-{jour[6:]}", "tx": _nombre(ligne["TX"])})
    return nom, sorted(jours, key=lambda j: j["date"])


def meteo(station: str, ete: int, client: httpx.Client) -> tuple[Provenance, list[dict]] | None:
    """Jours de l'été à la station ; ``None`` si la station n'a aucun jour cet été-là."""
    contenu = obtenir(client, "Météo-France", fichier(station, ete, client)).content
    nom, jours = lire_ete(contenu, station, ete)
    if not jours:
        return None
    return provenance(station, nom, ete), jours


def bilan(jours: list[dict]) -> dict:
    """Jours mesurés, jours à 30 °C ou plus et à 35 °C ou plus, maximum de l'été."""
    tx = [j["tx"] for j in jours if j.get("tx") is not None]
    return {
        "jours_mesures": len(tx),
        "jours_forte_chaleur": sum(t >= SEUIL_FORTE_CHALEUR_C for t in tx),
        "jours_tres_forte_chaleur": sum(t >= SEUIL_TRES_FORTE_CHALEUR_C for t in tx),
        "maximum_c": max(tx) if tx else None,
    }
