"""Aides pour exécuter un lot sans réseau (données figées, IA simulée)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image

from bitumap.ia.client import Appel, ReponseAge
from bitumap.lot import versions
from bitumap.lot.regional import DonneesRegionales
from bitumap.sources.fournisseur import FournisseurFige

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courbevoie"
IMAGES = [(a, Image.new("RGB", (8, 8), (40, 40, 40))) for a in (2011, 2018, 2024)]


def regional_fige(_dossier) -> DonneesRegionales:
    versions.enregistrer("osm", date(2026, 9, 27))
    versions.enregistrer("idfm", date(2026, 3, 31))
    versions.enregistrer("chaleur", versions.VERSION_CHALEUR)
    return DonneesRegionales(Path("inutile.gpkg"), date(2026, 9, 27), 0.1)


def fabrique_figee(insee: str) -> FournisseurFige:
    return FournisseurFige(FIXTURES, insee)


def vignettes_fixes(lon, lat):
    return IMAGES


def appel_ia_fixe(prompt, vignettes):
    reponse = ReponseAge(
        derniere_refection_debut=2014,
        derniere_refection_fin=2018,
        statut="visible",
        confiance=0.7,
        justification="Chaussée plus sombre entre les deux prises de vue.",
    )
    return Appel(reponse, reponse.model_dump_json(), 1500, 80)


def executer_lot(**kw):
    from bitumap.lot.__main__ import executer

    parametres = {
        "fabrique": fabrique_figee,
        "vignettes": vignettes_fixes,
        "appel_ia": appel_ia_fixe,
        "regional_fn": regional_fige,
    }
    parametres.update(kw)
    return executer(Path("inutile"), **parametres)
