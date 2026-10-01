"""Comptages de poids lourds publiés en données ouvertes, méthode 2.0 (004 R5, US3).

- **Hauts-de-Seine** : comptages routiers linéaires de la voirie départementale
  (data.iledefrance.fr, Licence Ouverte) ; trafic moyen journalier et % de poids lourds
  **par sens** ; comptages de 2009 à 2023, le % de poids lourds seulement depuis 2014.
- **Réseau routier national** : trafic moyen journalier annuel (data.gouv.fr, Licence
  Ouverte), **dernier millésime publié seulement**. Depuis 2022, ce millésime ne couvre que
  les autoroutes concédées ; le % de poids lourds du réseau non concédé d'Île-de-France de
  2019, dernier publié, est fautif (multiplié par 10) : ce réseau reste « non évalué »
  (décision du mainteneur, 2026-10-01). Trafic des deux sens confondus : chaque sens en
  porte la moitié.

Aucun autre département d'Île-de-France ne publie de comptage exploitable (inventaire T003) :
ses points restent « non évalués ».

Sortie commune, en Lambert 93 : ``source``, ``troncon`` (libellé affiché), ``numeros``
(numéros de route normalisés séparés par « ; »), ``libelle`` (adresse du compteur, pour le
rattachement par nom), ``pl_sens`` (poids lourds par jour du sens le plus chargé),
``annee`` (année du comptage). Garde-fou : un % de poids lourds hors de ]0, 100] écarte la
section.

Pas de cache : comme le LiDAR, les comptages sont relus à chaque rapport (une requête pour
le 92, une archive d'environ 2 Mo pour le réseau national).
"""

from __future__ import annotations

import re
import tempfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import shape

from bitumap.facteurs.voirie import normaliser_numero
from bitumap.sources.base import Extraction, Provenance, SourceIndisponible, obtenir

L93 = "EPSG:2154"
LICENCE = "Licence Ouverte (Etalab)"
COLONNES = ["source", "troncon", "numeros", "libelle", "pl_sens", "annee"]

JEU_92 = "comptages-routiers-lineaires-dans-les-hauts-de-seine"
URL_92 = f"https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/{JEU_92}/exports/geojson"
PAGE_92 = f"https://data.iledefrance.fr/explore/dataset/{JEU_92}/"
SOURCE_92 = "Hauts-de-Seine"

JEU_RRN = "trafic-moyen-journalier-annuel-sur-le-reseau-routier-national"
URL_RRN = f"https://www.data.gouv.fr/api/1/datasets/{JEU_RRN}/"
PAGE_RRN = f"https://www.data.gouv.fr/datasets/{JEU_RRN}"
SOURCE_RRN = "Réseau routier national"


def vide() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({c: [] for c in COLONNES}, geometry=[], crs=L93)


def numeros(texte) -> list[str]:
    """« A14, RN1014 » → [« A14 », « N1014 »] ; « A0005A » → [« A5A »] (zéros du réseau
    national retirés, comme dans la BD TOPO et OpenStreetMap)."""
    if texte is None or texte != texte:
        return []
    resultat = []
    for morceau in re.split(r"[,;/]", str(texte)):
        n = re.sub(r"^([A-Z]+)0+(?=\d)", r"\1", normaliser_numero(morceau))
        if n:
            resultat.append(n)
    return resultat


def _nombre(valeur) -> float | None:
    if valeur is None or valeur != valeur:
        return None
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def _part_valide(pourcentage: float | None) -> bool:
    return pourcentage is not None and 0 < pourcentage <= 100


def pl_par_sens_92(proprietes: dict) -> float | None:
    """Poids lourds par jour du sens le plus chargé, parmi les sens où trafic et % de poids
    lourds sont publiés ; ``None`` si aucun sens n'est complet."""
    sens = []
    for s in ("s1", "s2"):
        tmja, part = (
            _nombre(proprietes.get(f"tmja_{s}")),
            _nombre(proprietes.get(f"pourcentage_pl_{s}")),
        )
        if tmja and tmja > 0 and _part_valide(part):
            sens.append(tmja * part / 100)
    return max(sens) if sens else None


def _polygone(emprise: tuple[float, float, float, float]) -> str:
    minx, miny, maxx, maxy = emprise
    coins = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
    return "POLYGON((" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in coins) + "))"


def hauts_de_seine(emprise, client: httpx.Client) -> Extraction:
    reponse = obtenir(
        client,
        SOURCE_92,
        URL_92,
        params={
            "where": f"intersects(geo_shape, geom'{_polygone(emprise)}')",
            "select": "nom_voie,adresse_compteur,annee_comptage,tmja_s1,tmja_s2,"
            "pourcentage_pl_s1,pourcentage_pl_s2,geo_shape",
        },
    )
    lignes, geometries = [], []
    for entite in reponse.json().get("features", []):
        p = entite.get("properties") or {}
        pl = pl_par_sens_92(p)
        annee = _nombre(p.get("annee_comptage"))
        if pl is None or annee is None or not entite.get("geometry"):
            continue
        voie, adresse = str(p.get("nom_voie") or ""), str(p.get("adresse_compteur") or "")
        lignes.append(
            {
                "source": SOURCE_92,
                "troncon": f"{voie}, {adresse}" if adresse and adresse != voie else voie,
                "numeros": ";".join(numeros(voie)),
                "libelle": adresse,
                "pl_sens": round(pl, 1),
                "annee": int(annee),
            }
        )
        geometries.append(entite["geometry"])
    donnees = (
        gpd.GeoDataFrame(
            lignes,
            geometry=[shape(g) for g in geometries],
            crs="EPSG:4326",
        ).to_crs(L93)
        if lignes
        else vide()
    )
    return Extraction(
        Provenance(
            "Département des Hauts-de-Seine : comptages routiers (poids lourds)",
            LICENCE,
            PAGE_92,
            date.today(),
            "communale",
        ),
        donnees,
    )


def _dernier_shapefile(client: httpx.Client) -> tuple[int, str]:
    """Année et URL de l'archive shapefile du dernier millésime publié."""
    jeu = obtenir(client, SOURCE_RRN, URL_RRN).json()
    archives = []
    for r in jeu.get("resources", []):
        annee = re.search(r"(20\d\d)", str(r.get("title", "")))
        if annee and "shp" in str(r.get("title", "")).lower() + str(r.get("url", "")).lower():
            archives.append((int(annee.group(1)), str(r["url"])))
    if not archives:
        raise SourceIndisponible(SOURCE_RRN, "aucune archive shapefile")
    return max(archives)


def _colonne(gdf: gpd.GeoDataFrame, *noms: str) -> pd.Series:
    """Colonne par nom, sans tenir compte de la casse (les millésimes varient)."""
    par_nom = {c.lower(): c for c in gdf.columns}
    for nom in noms:
        if nom in par_nom:
            return gdf[par_nom[nom]]
    raise SourceIndisponible(SOURCE_RRN, f"colonne absente : {noms[0]}")


def lire_reseau_national(chemin: Path, emprise_l93) -> gpd.GeoDataFrame:
    """Sections d'une archive shapefile du réseau national, dans l'emprise (Lambert 93)."""
    gdf = gpd.read_file(chemin, bbox=emprise_l93)
    if gdf.empty:
        return vide()
    # Lambert 93 (IGNF:LAMB93 dans les fichiers récents, aucune projection en 2019).
    gdf = gdf.set_crs(L93, allow_override=True)
    tmja = pd.to_numeric(_colonne(gdf, "tmja"), errors="coerce")
    part = pd.to_numeric(_colonne(gdf, "pctpl", "ratio_pl", "ratiopl"), errors="coerce")
    annee = pd.to_numeric(_colonne(gdf, "anneemesur", "anneemesuretrafic"), errors="coerce")
    garde = (tmja > 0) & (part > 0) & (part <= 100) & annee.notna()
    route = _colonne(gdf, "route")[garde]
    sortie = gpd.GeoDataFrame(
        {
            "source": SOURCE_RRN,
            "troncon": route.map(lambda r: "".join(numeros(r)) or str(r)),
            "numeros": route.map(lambda r: ";".join(numeros(r))),
            "libelle": "",
            "pl_sens": (tmja[garde] * part[garde] / 100 / 2).round(1),
            "annee": annee[garde].astype(int),
        },
        geometry=gdf.geometry[garde],
        crs=L93,
    )
    return sortie.reset_index(drop=True) if not sortie.empty else vide()


def reseau_national(emprise, client: httpx.Client) -> Extraction:
    annee, url = _dernier_shapefile(client)
    emprise_l93 = tuple(
        gpd.GeoSeries.from_xy(emprise[::2], emprise[1::2], crs="EPSG:4326").to_crs(L93).total_bounds
    )
    with tempfile.TemporaryDirectory() as dossier:
        archive = Path(dossier) / "rrn.zip"
        archive.write_bytes(obtenir(client, SOURCE_RRN, url).content)
        donnees = lire_reseau_national(archive, emprise_l93)
    return Extraction(
        Provenance(
            f"Ministère chargé des transports : trafic moyen journalier annuel du réseau "
            f"routier national ({annee})",
            LICENCE,
            PAGE_RRN,
            date.today(),
            "regionale",
        ),
        donnees,
    )


def acquerir(emprise, client: httpx.Client) -> tuple[list[Provenance], gpd.GeoDataFrame]:
    """Comptages de toutes les sources retenues, dans l'emprise (degrés)."""
    extractions = [hauts_de_seine(emprise, client), reseau_national(emprise, client)]
    morceaux = [e.donnees for e in extractions if not e.donnees.empty]
    donnees = (
        gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=L93) if morceaux else vide()
    )
    return [e.provenance for e in extractions], donnees
