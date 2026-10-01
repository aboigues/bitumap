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
from pyproj import Transformer

from bitumap.sources import (
    altimetrie,
    bdtopo,
    chaleur,
    comptages,
    idfm,
    lidar,
    ortho,
    osm,
    panoramax,
)
from bitumap.sources.base import Hauteurs, Provenance, Raster, client_http
from bitumap.territoire import api_geo

_VERS_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)


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

    # Méthode 2.0 (004) : appelés seulement si BITUMAP_METHODE=2.0 ; ``None`` = absent.
    def hauteurs(self, lon: float, lat: float) -> Hauteurs | None: ...
    def temperature_surface(self, emprise, ete: int) -> tuple[Provenance, Raster] | None: ...
    def comptages_pl(self, emprise) -> tuple[list[Provenance], gpd.GeoDataFrame | None]: ...
    def meteo(self, station: str, ete: int) -> tuple[Provenance, list[dict]] | None: ...


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
        self._millesimes_lidar: dict[str, str] = {}  # une requête d'index par dalle de 1 km

    def contour(self) -> dict:
        return api_geo.contour_geojson(self.insee)

    def hauteurs(self, lon, lat):
        x, y = _VERS_L93.transform(lon, lat)
        return lidar.hauteurs(x, y, self._client, self._millesimes_lidar)

    def comptages_pl(self, emprise):
        return comptages.acquerir(emprise, self._client)

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
        d["nom"],
        d["licence"],
        d["url"],
        date.fromisoformat(d["date_extraction"]),
        d["portee"],
        d.get("hors_ue", False),
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
        self._haut: dict[str, Hauteurs] = {}

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

    def hauteurs(self, lon, lat):
        h = self._s.hauteurs(lon, lat)
        if h is not None:
            self._haut[_cle(lon, lat)] = h
        return h

    def temperature_surface(self, emprise, ete):
        r = self._s.temperature_surface(emprise, ete)
        if r is not None:
            p, raster = r
            np.savez_compressed(
                self._d / "temperature.npz",
                valeurs=raster.valeurs,
                transform=np.array(raster.transform),
            )
            _ecrire_json(
                self._d / "temperature.json.gz",
                {"provenance": _prov_dict(p), "crs": raster.crs, "ete": raster.ete},
            )
        return r

    def comptages_pl(self, emprise):
        provs, gdf = self._s.comptages_pl(emprise)
        if gdf is not None:
            gdf.to_file(self._d / "comptages.gpkg", layer="comptages", driver="GPKG")
        _ecrire_json(self._d / "comptages_provenance.json.gz", [_prov_dict(p) for p in provs])
        return provs, gdf

    def meteo(self, station, ete):
        r = self._s.meteo(station, ete)
        if r is not None:
            _ecrire_json(
                self._d / "meteo.json.gz",
                {"station": station, "ete": ete, "provenance": _prov_dict(r[0]), "jours": r[1]},
            )
        return r

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
        if self._haut:
            ecrire_hauteurs(self._d / "hauteurs.npz", self._haut)


# Hauteurs figées au décimètre (dépôt léger) : entiers 16 bits au-dessus d'une base par point ;
# 65535 = pas de mesure. Largement assez précis pour des ombres.
_HAUTEUR_ABSENTE = np.iinfo(np.uint16).max


def _coder(grille: np.ndarray, base: float) -> np.ndarray:
    dm = np.round((grille - base) * 10)
    return np.where(np.isfinite(dm), np.clip(dm, 0, _HAUTEUR_ABSENTE - 1), _HAUTEUR_ABSENTE).astype(
        np.uint16
    )


def _decoder(codes: np.ndarray, base: float) -> np.ndarray:
    grille = codes.astype(np.float32) / 10 + np.float32(base)
    grille[codes == _HAUTEUR_ABSENTE] = np.nan
    return grille


def ecrire_hauteurs(chemin: Path, hauteurs: dict[str, Hauteurs]) -> None:
    """Fige les hauteurs LiDAR (004) ; relues par ``FournisseurFige``."""
    h = list(hauteurs.values())
    bases = [float(np.floor(np.nanmin(x.mnt))) - 1 if np.isfinite(x.mnt).any() else 0.0 for x in h]
    np.savez_compressed(
        chemin,
        cles=np.array(list(hauteurs)),
        mns=np.array([_coder(x.mns, b) for x, b in zip(h, bases, strict=True)]),
        mnt=np.array([_coder(x.mnt, b) for x, b in zip(h, bases, strict=True)]),
        bases=np.array(bases),
        origines=np.array([x.origine for x in h]),
        resolutions=np.array([x.resolution for x in h]),
        millesimes=np.array([x.millesime for x in h]),
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
        self._haut: dict[str, Hauteurs] = {}
        if (dossier / "hauteurs.npz").exists():  # absent des dossiers figés avant 004
            h = np.load(dossier / "hauteurs.npz")
            for i, cle in enumerate(h["cles"].tolist()):
                base = float(h["bases"][i])
                self._haut[cle] = Hauteurs(
                    _decoder(h["mns"][i], base),
                    _decoder(h["mnt"][i], base),
                    tuple(float(c) for c in h["origines"][i]),
                    float(h["resolutions"][i]),
                    str(h["millesimes"][i]),
                )

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

    def hauteurs(self, lon, lat):
        return self._haut.get(_cle(lon, lat))

    def temperature_surface(self, emprise, ete):
        meta = self._d / "temperature.json.gz"
        if not meta.exists():
            return None
        m = _lire_json(meta)
        if m["ete"] != ete:
            return None
        t = np.load(self._d / "temperature.npz")
        transform = tuple(float(c) for c in t["transform"])
        return _prov(m["provenance"]), Raster(t["valeurs"], transform, m["crs"], m["ete"])

    def comptages_pl(self, emprise):
        meta = self._d / "comptages_provenance.json.gz"
        if not meta.exists():
            return [], None
        provs = [_prov(d) for d in _lire_json(meta)]
        f = self._d / "comptages.gpkg"
        return provs, gpd.read_file(f, layer="comptages") if f.exists() else None

    def meteo(self, station, ete):
        f = self._d / "meteo.json.gz"
        if not f.exists():
            return None
        m = _lire_json(f)
        if (m["station"], m["ete"]) != (station, ete):
            return None
        return _prov(m["provenance"]), m["jours"]
