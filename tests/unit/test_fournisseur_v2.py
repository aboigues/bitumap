"""Données de la méthode 2.0 figées puis relues sans réseau (004 T009) ; champs du modèle
ajoutés sans changer la sortie 1.2 (T008)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString

from bitumap.modele import Facteur, Point
from bitumap.sources.base import Hauteurs, Provenance, Raster
from bitumap.sources.fournisseur import Enregistreur, FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"
PROV = Provenance(
    "Source de test", "Licence Ouverte", "https://exemple.fr", date(2026, 9, 30), "communale"
)
PROV_HORS_UE = Provenance(
    "USGS", "Domaine public", "https://usgs.gov", date(2026, 9, 30), "communale", hors_ue=True
)


class _EnLigne:
    """Remplace le fournisseur en ligne : réponses fixes, aucun réseau."""

    insee = "92026"

    def hauteurs(self, lon, lat):
        if lon > 3:
            return None  # dalle absente
        mns = np.full((4, 4), 45.5, dtype=np.float32)
        mns[0, 0] = np.nan  # pas de mesure
        mnt = np.full((4, 4), 35.25, dtype=np.float32)
        return Hauteurs(mns, mnt, (645000.0, 6867200.0), 1.0, "22LHDKE 2023-03-03")

    def temperature_surface(self, emprise, ete):
        valeurs = np.array([[32.0, np.nan], [37.4, 35.0]], dtype=np.float32)
        return PROV_HORS_UE, Raster(
            valeurs, (645000.0, 30.0, 0.0, 6867300.0, 0.0, -30.0), "EPSG:32631", ete
        )

    def comptages_pl(self, emprise):
        gdf = gpd.GeoDataFrame(
            {"route": ["D7"], "pl_jour": [3200.0], "annee": [2021], "source": ["CD92"]},
            geometry=[LineString([(645000, 6867000), (645100, 6867050)])],
            crs="EPSG:2154",
        )
        return [PROV], gdf

    def meteo(self, station, ete):
        return PROV, [{"jour": "2026-07-01", "tx": 36.1}, {"jour": "2026-07-02", "tx": 29.0}]

    def provenances_ponctuelles(self):
        return []


def test_aller_retour_des_donnees_v2(tmp_path):
    e = Enregistreur(_EnLigne(), tmp_path)
    h = e.hauteurs(2.2606, 48.9008)
    assert e.hauteurs(3.5, 48.9) is None
    t = e.temperature_surface((2.23, 48.88, 2.29, 48.91), 2026)
    c = e.comptages_pl((2.23, 48.88, 2.29, 48.91))
    m = e.meteo("75114001", 2026)
    e.terminer()

    f = FournisseurFige(tmp_path, "92026")
    h2 = f.hauteurs(2.2606, 48.9008)
    # figées au décimètre (dépôt léger), « pas de mesure » conservé
    assert np.allclose(h2.mns, h.mns, atol=0.051, equal_nan=True)
    assert np.allclose(h2.mnt, h.mnt, atol=0.051) and np.isnan(h2.mns[0, 0])
    assert h2.mns.dtype == np.float32
    assert (h2.origine, h2.resolution, h2.millesime) == (h.origine, h.resolution, h.millesime)
    assert f.hauteurs(3.5, 48.9) is None
    prov, raster = f.temperature_surface((2.23, 48.88, 2.29, 48.91), 2026)
    assert prov.hors_ue and raster.ete == 2026 and raster.transform == t[1].transform
    assert np.array_equal(raster.valeurs, t[1].valeurs, equal_nan=True)
    provs, gdf = f.comptages_pl(None)
    assert provs == c[0] and gdf.iloc[0]["pl_jour"] == 3200.0 and gdf.crs.to_epsg() == 2154
    assert f.meteo("75114001", 2026) == m


def test_dossier_fige_sans_donnees_v2():
    # Un dossier figé avant 004 reste lisible : les accès 2.0 répondent « absent ».
    f = FournisseurFige(FIXTURES, "92026")
    assert f.hauteurs(2.26, 48.9) is None
    assert f.temperature_surface(None, 2026) is None
    assert f.comptages_pl(None) == ([], None)
    assert f.meteo("75114001", 2026) is None


def test_provenance_hors_ue_seulement_si_declaree():
    assert "hors_ue" not in PROV.en_dict()
    assert PROV_HORS_UE.en_dict()["hors_ue"] is True


def test_champs_v2_absents_de_la_sortie_1_2():
    p = Point(
        id="A1", type="arret", nom="x", lon=2.2, lat=48.9, facteurs=[Facteur("charge", 1, 1.0)]
    )
    d = p.en_dict()
    assert "niveau_v1" not in d and "raison_changement" not in d
    assert "details" not in d["facteurs"][0]
    assert set(asdict(p.facteurs[0])) >= {"details"}


def test_champs_v2_presents_quand_renseignes():
    f = Facteur("ensoleillement", 6.5, 1.1, details={"cause_ombre": "arbre", "source": "lidar_hd"})
    p = Point(id="A1", type="arret", nom="x", lon=2.2, lat=48.9, facteurs=[f])
    p.niveau_v1, p.raison_changement = "P1b", "chaleur"
    d = p.en_dict()
    assert d["niveau_v1"] == "P1b" and d["raison_changement"] == "chaleur"
    assert d["facteurs"][0]["details"]["cause_ombre"] == "arbre"
