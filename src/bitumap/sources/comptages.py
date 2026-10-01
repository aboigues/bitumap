"""Comptages de poids lourds publiés en données ouvertes, méthode 2.0 (004 R5, US3).

Les sources sont déclarées dans le catalogue versionné ``comptages.toml`` (jeu, champs,
licence) et lues par un **lecteur générique par plateforme** :

- ``opendatasoft`` : API Explore v2.1 (portails de la région et des départements), sections
  qui coupent l'emprise ;
- ``datagouv_shapefile`` : archive shapefile d'un jeu de data.gouv.fr, **dernier millésime
  publié** (réseau routier national : depuis 2022, autoroutes concédées seulement ; le
  réseau non concédé reste « non évalué », LL-018).

Ajouter un département qui publie sur une de ces plateformes = ajouter une entrée au
catalogue. Poids lourds par sens : trafic du sens × % de poids lourds du sens, sens le plus
chargé parmi les sens complets ; quand seul le total des deux sens est publié, chaque sens en
porte la moitié. Garde-fou : un % de poids lourds hors de ]0, 100] écarte la valeur.

Sortie commune, en Lambert 93 : ``source`` (étiquette), ``troncon`` (libellé affiché),
``numeros`` (numéros de route normalisés séparés par « ; »), ``libelle`` (adresse du
compteur, pour le rattachement par nom), ``pl_sens``, ``annee``.

Pas de cache : comme le LiDAR, les comptages sont relus à chaque rapport.
"""

from __future__ import annotations

import re
import tempfile
import tomllib
from datetime import date
from importlib import resources
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import shape

from bitumap.facteurs.voirie import normaliser_numero
from bitumap.sources.base import (
    Extraction,
    Provenance,
    SourceIndisponible,
    obtenir,
    telecharger,
    verifier_url,
)

L93 = "EPSG:2154"
COLONNES = ["source", "troncon", "numeros", "libelle", "pl_sens", "annee"]
URL_DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/{jeu}/"
# Fichiers des jeux de data.gouv.fr : hôtes de stockage de la plateforme seulement ; taille
# bornée (archive du réseau national : environ 2 Mo en 2024).
HOTES_DATAGOUV = ("static.data.gouv.fr", "object.files.data.gouv.fr")
MAX_ARCHIVE_OCTETS = 50_000_000


def catalogue() -> list[dict]:
    """Sources déclarées dans ``comptages.toml``, dans l'ordre du fichier."""
    texte = (resources.files("bitumap.sources") / "comptages.toml").read_text("utf-8")
    sources = tomllib.loads(texte)["source"]
    for s in sources:
        if s["type"] not in LECTEURS:
            raise ValueError(f"comptages.toml : type inconnu pour {s['id']} : {s['type']}")
    return sources


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


def _noms(champ) -> list[str]:
    return [champ] if isinstance(champ, str) else list(champ)


def _valeur(proprietes: dict, champ):
    """Valeur du premier nom de champ présent, sans tenir compte de la casse."""
    if champ is None:
        return None
    par_nom = {k.lower(): v for k, v in proprietes.items()}
    for nom in _noms(champ):
        if nom.lower() in par_nom:
            return par_nom[nom.lower()]
    return None


def _pl(tmja, part, diviseur: int = 1) -> float | None:
    tmja, part = _nombre(tmja), _nombre(part)
    if not tmja or tmja <= 0 or part is None or not 0 < part <= 100:
        return None
    return tmja * part / 100 / diviseur


def pl_par_sens(proprietes: dict, champs: dict) -> float | None:
    """Poids lourds par jour du sens le plus chargé ; ``None`` si aucun sens n'est complet."""
    if "sens" in champs:
        valeurs = [
            _pl(_valeur(proprietes, s["tmja"]), _valeur(proprietes, s["pct_pl"]))
            for s in champs["sens"]
        ]
    else:
        valeurs = [
            _pl(
                _valeur(proprietes, champs["tmja_deux_sens"]),
                _valeur(proprietes, champs["pct_pl"]),
                diviseur=2,
            )
        ]
    valeurs = [v for v in valeurs if v is not None]
    return max(valeurs) if valeurs else None


def _troncon(numero_brut: str, libelle: str) -> str:
    """« RD7, 23 quai… » ; « A0014 » → « A14 » (zéros de remplissage retirés)."""
    numero = re.sub(r"\b([A-Z]+)0+(?=\d)", r"\1", numero_brut)
    return f"{numero}, {libelle}" if libelle and libelle != numero_brut else numero


def sections(source: dict, enregistrements, crs: str) -> gpd.GeoDataFrame:
    """Normalise des enregistrements ``(propriétés, géométrie shapely)`` d'une source."""
    champs = source["champs"]
    lignes, geometries = [], []
    for proprietes, geometrie in enregistrements:
        pl = pl_par_sens(proprietes, champs)
        annee = _nombre(_valeur(proprietes, champs["annee"]))
        if pl is None or annee is None or geometrie is None or geometrie.is_empty:
            continue
        brut = str(_valeur(proprietes, champs["numero"]) or "")
        libelle = str(_valeur(proprietes, champs.get("libelle")) or "")
        lignes.append(
            {
                "source": source["etiquette"],
                "troncon": _troncon(brut, libelle),
                "numeros": ";".join(numeros(brut)),
                "libelle": libelle,
                "pl_sens": round(pl, 1),
                "annee": int(annee),
            }
        )
        geometries.append(geometrie)
    if not lignes:
        return vide()
    return gpd.GeoDataFrame(lignes, geometry=geometries, crs=crs).to_crs(L93)


def _provenance(source: dict, millesime: int | None = None) -> Provenance:
    nom = source["nom"].format(millesime=millesime if millesime is not None else "")
    return Provenance(
        nom.replace(" ()", ""),
        source["licence"],
        source["page"],
        date.today(),
        source["portee"],
    )


def _polygone(emprise: tuple[float, float, float, float]) -> str:
    minx, miny, maxx, maxy = emprise
    coins = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
    return "POLYGON((" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in coins) + "))"


def url_opendatasoft(source: dict) -> str:
    return f"{source['portail']}/api/explore/v2.1/catalog/datasets/{source['jeu']}/exports/geojson"


def lire_opendatasoft(source: dict, emprise, client: httpx.Client) -> Extraction:
    """Sections d'un jeu Opendatasoft qui coupent l'emprise (degrés)."""
    geometrie = source.get("geometrie", "geo_shape")
    reponse = obtenir(
        client,
        source["etiquette"],
        url_opendatasoft(source),
        params={"where": f"intersects({geometrie}, geom'{_polygone(emprise)}')"},
    )
    enregistrements = [
        (e.get("properties") or {}, shape(e["geometry"]) if e.get("geometry") else None)
        for e in reponse.json().get("features", [])
    ]
    return Extraction(_provenance(source), sections(source, enregistrements, "EPSG:4326"))


def _dernier_shapefile(source: dict, client: httpx.Client) -> tuple[int, str]:
    """Année et URL de l'archive shapefile du dernier millésime publié."""
    jeu = obtenir(client, source["etiquette"], URL_DATAGOUV.format(jeu=source["jeu"])).json()
    archives = []
    for r in jeu.get("resources", []):
        titre = str(r.get("title", ""))
        annee = re.search(r"(20\d\d)", titre)
        if annee and "shp" in titre.lower() + str(r.get("url", "")).lower():
            archives.append((int(annee.group(1)), str(r["url"])))
    if not archives:
        raise SourceIndisponible(source["etiquette"], "aucune archive shapefile")
    return max(archives)


def lire_archive(source: dict, chemin: Path, emprise_l93) -> gpd.GeoDataFrame:
    """Sections d'une archive shapefile en Lambert 93, dans l'emprise."""
    gdf = gpd.read_file(chemin, bbox=emprise_l93)
    if gdf.empty:
        return vide()
    # Lambert 93 (IGNF:LAMB93 dans les fichiers récents du réseau national, sans projection
    # en 2019).
    gdf = gdf.set_crs(L93, allow_override=True)
    proprietes = gdf.drop(columns="geometry").to_dict("records")
    return sections(source, zip(proprietes, gdf.geometry, strict=True), L93)


def lire_datagouv_shapefile(source: dict, emprise, client: httpx.Client) -> Extraction:
    if source.get("millesime", "dernier") != "dernier":
        raise ValueError(f"comptages.toml : millésime non pris en charge pour {source['id']}")
    annee, url = _dernier_shapefile(source, client)
    coins = gpd.GeoSeries.from_xy(emprise[::2], emprise[1::2], crs="EPSG:4326").to_crs(L93)
    with tempfile.TemporaryDirectory() as dossier:
        archive = Path(dossier) / "comptages.zip"
        verifier_url(source["etiquette"], url, HOTES_DATAGOUV)
        archive.write_bytes(telecharger(client, source["etiquette"], url, MAX_ARCHIVE_OCTETS))
        donnees = lire_archive(source, archive, tuple(coins.total_bounds))
    return Extraction(_provenance(source, annee), donnees)


LECTEURS = {"opendatasoft": lire_opendatasoft, "datagouv_shapefile": lire_datagouv_shapefile}


def acquerir(
    emprise, client: httpx.Client, sources: list[dict] | None = None
) -> tuple[list[Provenance], gpd.GeoDataFrame]:
    """Comptages de toutes les sources du catalogue, dans l'emprise (degrés)."""
    extractions = [LECTEURS[s["type"]](s, emprise, client) for s in (sources or catalogue())]
    morceaux = [e.donnees for e in extractions if not e.donnees.empty]
    donnees = (
        gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=L93) if morceaux else vide()
    )
    return [e.provenance for e in extractions], donnees
