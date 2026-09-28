"""Fournisseurs de données pour le calcul d'une commune.

- ``FournisseurEnLigne`` : interroge les sources (production) ;
- ``Enregistreur`` : enveloppe un fournisseur en ligne et fige ses réponses dans un dossier
  (``tools/figer_fixtures.py``) ;
- ``FournisseurFige`` : relit un dossier figé (tests, non-régression, sans réseau).

Le calcul (``bitumap.calcul``) ne connaît que l'interface commune ci-dessous.
"""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path
from typing import Protocol

import geopandas as gpd
import numpy as np

from bitumap.sources import altimetrie, bdtopo, chaleur, idfm, ortho, osm, panoramax
from bitumap.sources.base import Provenance, client_http
from bitumap.territoire import api_geo


class Fournisseur(Protocol):
    insee: str

    def contour(self) -> dict: ...
    def offre(self) -> tuple[Provenance, list[dict]]: ...
    def osm(self, emprise) -> tuple[Provenance, osm.DonneesOsm]: ...
    def bdtopo(self, emprise) -> tuple[Provenance, dict[str, gpd.GeoDataFrame]]: ...
    def chaleur(self, emprise) -> tuple[Provenance, gpd.GeoDataFrame]: ...
    def altitudes(self, points: list[tuple[float, float]]) -> list[float | None]: ...
    def vegetation(self, lon: float, lat: float) -> np.ndarray | None: ...
    def panoramax(self, lon: float, lat: float) -> panoramax.Photo | None: ...
    def provenances_ponctuelles(self) -> list[Provenance]: ...


# Paramètres fixes des extractions ponctuelles (identiques en ligne et figé).
VEGETATION_DEMI_COTE_M = 100
VEGETATION_RESOLUTION_M = 1.0
PANORAMAX_RAYON_M = 30


def _cle(lon: float, lat: float) -> str:
    return f"{lon:.6f},{lat:.6f}"


class FournisseurEnLigne:
    def __init__(self, insee: str, osm_regional: Path, osm_date: date):
        self.insee = insee
        self._osm_regional = osm_regional
        self._osm_date = osm_date
        self._client = client_http(timeout=120)

    def contour(self) -> dict:
        return api_geo.contour_geojson(self.insee)

    def offre(self):
        maj = idfm.date_mise_a_jour(self._client)
        from bitumap.sources.base import obtenir

        lignes = obtenir(
            self._client,
            "IDFM",
            f"{idfm.URL}/exports/json",
            params={"where": f'code_commune="{self.insee}" AND libelle_mode_ligne="Bus"'},
        ).json()
        return (
            Provenance(
                "IDFM : offre hebdomadaire moyenne hors vacances",
                idfm.LICENCE,
                idfm.URL,
                maj,
                "communale",
            ),
            lignes,
        )

    def osm(self, emprise):
        e = osm.extraction_communale(self._osm_regional, self._osm_date, emprise)
        return e.provenance, e.donnees

    def bdtopo(self, emprise):
        e = bdtopo.acquerir(emprise, self._client)
        return e.provenance, e.donnees

    def chaleur(self, emprise):
        e = chaleur.acquerir(emprise, self._client)
        return e.provenance, e.donnees

    def altitudes(self, points):
        return altimetrie.altitudes(points, self._client)

    def vegetation(self, lon, lat):
        return ortho.masque_vegetation(
            lon, lat, VEGETATION_DEMI_COTE_M, VEGETATION_RESOLUTION_M, self._client
        )

    def panoramax(self, lon, lat):
        return panoramax.photo_la_plus_recente(lon, lat, PANORAMAX_RAYON_M, self._client)

    def provenances_ponctuelles(self):
        return [altimetrie.provenance(), ortho.provenance(), panoramax.provenance()]

    def fermer(self):
        self._client.close()


def _ecrire_json(chemin: Path, donnees) -> None:
    with gzip.open(chemin, "wt", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, default=str)


def _lire_json(chemin: Path):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        return json.load(f)


def _prov_dict(p: Provenance) -> dict:
    return p.en_dict()


def _prov(d: dict) -> Provenance:
    return Provenance(
        d["nom"], d["licence"], d["url"], date.fromisoformat(d["date_extraction"]), d["portee"]
    )


class Enregistreur:
    """Enveloppe un fournisseur et fige chaque réponse dans ``dossier``."""

    def __init__(self, source: FournisseurEnLigne, dossier: Path):
        self._s = source
        self.insee = source.insee
        self._d = dossier
        dossier.mkdir(parents=True, exist_ok=True)
        self._alt: dict[str, float | None] = {}
        self._veg: dict[str, np.ndarray | None] = {}
        self._pnx: dict[str, dict | None] = {}

    def contour(self):
        c = self._s.contour()
        _ecrire_json(self._d / "contour.json.gz", c)
        return c

    def offre(self):
        p, lignes = self._s.offre()
        _ecrire_json(self._d / "offre.json.gz", {"provenance": _prov_dict(p), "lignes": lignes})
        return p, lignes

    def osm(self, emprise):
        p, d = self._s.osm(emprise)
        for couche in osm.COUCHES:
            getattr(d, couche).to_file(self._d / "osm.gpkg", layer=couche, driver="GPKG")
        _ecrire_json(self._d / "osm_provenance.json.gz", _prov_dict(p))
        return p, d

    def bdtopo(self, emprise):
        p, d = self._s.bdtopo(emprise)
        for couche, gdf in d.items():
            gdf.to_file(self._d / "bdtopo.gpkg", layer=couche, driver="GPKG")
        _ecrire_json(self._d / "bdtopo_provenance.json.gz", _prov_dict(p))
        return p, d

    def chaleur(self, emprise):
        p, d = self._s.chaleur(emprise)
        d.to_file(self._d / "chaleur.gpkg", layer="chaleur", driver="GPKG")
        _ecrire_json(self._d / "chaleur_provenance.json.gz", _prov_dict(p))
        return p, d

    def altitudes(self, points):
        valeurs = self._s.altitudes(points)
        self._alt.update({_cle(*pt): v for pt, v in zip(points, valeurs, strict=True)})
        return valeurs

    def vegetation(self, lon, lat):
        m = self._s.vegetation(lon, lat)
        self._veg[_cle(lon, lat)] = m
        return m

    def panoramax(self, lon, lat):
        p = self._s.panoramax(lon, lat)
        self._pnx[_cle(lon, lat)] = None if p is None else p.__dict__
        return p

    def provenances_ponctuelles(self):
        return self._s.provenances_ponctuelles()

    def terminer(self):
        _ecrire_json(self._d / "altitudes.json.gz", self._alt)
        _ecrire_json(self._d / "panoramax.json.gz", self._pnx)
        _ecrire_json(
            self._d / "provenances_ponctuelles.json.gz",
            [_prov_dict(p) for p in self._s.provenances_ponctuelles()],
        )
        presents = {k: v for k, v in self._veg.items() if v is not None}
        np.savez_compressed(
            self._d / "vegetation.npz",
            cles=np.array(list(presents)),
            masques=np.array(list(presents.values())) if presents else np.zeros((0, 1, 1), bool),
        )


class FournisseurFige:
    """Relit un dossier produit par ``Enregistreur`` : aucun accès réseau."""

    def __init__(self, dossier: Path, insee: str):
        self.insee = insee
        self._d = dossier
        self._alt = _lire_json(dossier / "altitudes.json.gz")
        self._pnx = _lire_json(dossier / "panoramax.json.gz")
        v = np.load(dossier / "vegetation.npz")
        self._veg = dict(zip(v["cles"].tolist(), v["masques"], strict=True))

    def contour(self):
        return _lire_json(self._d / "contour.json.gz")

    def offre(self):
        d = _lire_json(self._d / "offre.json.gz")
        return _prov(d["provenance"]), d["lignes"]

    def osm(self, emprise):
        f = self._d / "osm.gpkg"
        donnees = osm.DonneesOsm(*(gpd.read_file(f, layer=c) for c in osm.COUCHES))
        return _prov(_lire_json(self._d / "osm_provenance.json.gz")), donnees

    def bdtopo(self, emprise):
        f = self._d / "bdtopo.gpkg"
        d = {c: gpd.read_file(f, layer=c) for c in ("troncons", "batiments")}
        return _prov(_lire_json(self._d / "bdtopo_provenance.json.gz")), d

    def chaleur(self, emprise):
        d = gpd.read_file(self._d / "chaleur.gpkg", layer="chaleur")
        return _prov(_lire_json(self._d / "chaleur_provenance.json.gz")), d

    def altitudes(self, points):
        return [self._alt.get(_cle(*pt)) for pt in points]

    def vegetation(self, lon, lat):
        return self._veg.get(_cle(lon, lat))

    def panoramax(self, lon, lat):
        d = self._pnx.get(_cle(lon, lat))
        return None if d is None else panoramax.Photo(**d)

    def provenances_ponctuelles(self):
        return [_prov(d) for d in _lire_json(self._d / "provenances_ponctuelles.json.gz")]
