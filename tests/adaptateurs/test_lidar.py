"""Adaptateur LiDAR HD (004 T013, R1) : réponses HTTP simulées, aucun réseau."""

from __future__ import annotations

import httpx
import numpy as np
import respx
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from bitumap.sources import lidar

X, Y = 645794.3, 6867009.8  # « Paix - Verdun », Courbevoie (Lambert 93)


def _geotiff(valeurs: np.ndarray, x0: float, y0: float) -> bytes:
    with MemoryFile() as m:
        with m.open(
            driver="GTiff",
            width=valeurs.shape[1],
            height=valeurs.shape[0],
            count=1,
            dtype="float32",
            crs="EPSG:2154",
            transform=from_origin(x0, y0, 1.0, 1.0),
            nodata=-9999.0,
        ) as ds:
            ds.write(valeurs.astype("float32"), 1)
        return m.read()


def _index(code="22LHDKE", acquisition="2023-03-03Z"):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "coordonnees_nw": "0645-6868",
                    "code_mission": code,
                    "date_fin_acquisition": acquisition,
                    "date_edition": "2025-06-06Z",
                },
            }
        ],
    }


def _simuler(mns: np.ndarray, mnt: np.ndarray, index=None):
    cote = lidar.DEMI_COTE_M * 2
    x0, y0 = X - lidar.DEMI_COTE_M, Y + lidar.DEMI_COTE_M

    def repondre(requete):
        couche = requete.url.params["LAYERS"]
        assert requete.url.params["CRS"] == "EPSG:2154"
        assert requete.url.params["WIDTH"] == str(cote)
        valeurs = mns if "MNS" in couche else mnt
        return httpx.Response(
            200, headers={"content-type": "image/geotiff"}, content=_geotiff(valeurs, x0, y0)
        )

    respx.get(lidar.URL_WMS).mock(side_effect=repondre)
    respx.get(lidar.URL_WFS).mock(return_value=httpx.Response(200, json=index or _index()))


@respx.mock
def test_hauteurs_autour_d_un_point():
    cote = lidar.DEMI_COTE_M * 2
    mns = np.full((cote, cote), 45.5, dtype=np.float32)
    mns[0, 0] = -9999.0  # nodata
    mnt = np.full((cote, cote), 35.25, dtype=np.float32)
    _simuler(mns, mnt)
    with httpx.Client() as client:
        h = lidar.hauteurs(X, Y, client, {})
    assert h.mns.shape == h.mnt.shape == (cote, cote)
    assert np.isnan(h.mns[0, 0]) and h.mns[1, 1] == 45.5 and h.mnt[5, 5] == 35.25
    assert h.origine == (X - lidar.DEMI_COTE_M, Y + lidar.DEMI_COTE_M)
    assert h.resolution == 1.0
    assert h.millesime == "22LHDKE 2023-03-03"


@respx.mock
def test_millesime_lu_une_fois_par_dalle():
    cote = lidar.DEMI_COTE_M * 2
    plan = np.full((cote, cote), 40.0, dtype=np.float32)
    _simuler(plan, plan)
    memo: dict[str, str] = {}
    with httpx.Client() as client:
        lidar.hauteurs(X, Y, client, memo)
        lidar.hauteurs(X + 5, Y + 5, client, memo)  # même dalle de 1 km
    assert len(respx.calls) == 2 * 2 + 1  # deux fois MNS + MNT, index une seule fois
    assert memo == {"0645-6868": "22LHDKE 2023-03-03"}


def test_dalle_d_un_point():
    assert lidar.dalle(645794.3, 6867009.8) == "0645-6868"
    assert lidar.dalle(645000.0, 6867999.9) == "0645-6868"


@respx.mock
def test_zone_non_couverte():
    cote = lidar.DEMI_COTE_M * 2
    vide = np.full((cote, cote), -9999.0, dtype=np.float32)
    _simuler(vide, vide, index={"type": "FeatureCollection", "features": []})
    with httpx.Client() as client:
        assert lidar.hauteurs(X, Y, client, {}) is None


@respx.mock
def test_erreur_du_service_rend_none():
    respx.get(lidar.URL_WMS).mock(
        return_value=httpx.Response(
            200, headers={"content-type": "text/xml"}, text="<ServiceException/>"
        )
    )
    respx.get(lidar.URL_WFS).mock(return_value=httpx.Response(200, json=_index()))
    with httpx.Client() as client:
        assert lidar.hauteurs(X, Y, client, {}) is None


def test_provenance():
    p = lidar.provenance()
    assert p.nom.startswith("IGN LiDAR HD")
    assert p.licence == "Licence Ouverte Etalab 2.0"
    assert not p.hors_ue
