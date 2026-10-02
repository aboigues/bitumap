"""Points du rapport en vigueur d'une commune (003, T009) : ceux auxquels se rattachent les
relevés (identifiant stable, 002 FR-016)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from bitumap import stockage
from bitumap.config import reglages


@dataclass(frozen=True)
class PointRapport:
    id: str
    nom: str
    designation: str
    groupe: str
    rang: int
    lon: float
    lat: float


def rapport_en_vigueur(insee: str) -> str | None:
    """Empreinte du rapport en vigueur de la commune (même règle que le cache de 002)."""
    from bitumap.api.demandes import rapport_valide  # import tardif : évite un cycle

    return rapport_valide(insee)


def points_du_rapport(insee: str, empreinte: str) -> dict[str, PointRapport]:
    contenu = stockage.lire(
        reglages().bucket_rapports, stockage.prefixe_rapport(insee, empreinte) + "points.geojson"
    )
    if contenu is None:
        return {}
    points = {}
    for f in json.loads(contenu)["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        points[p["id"]] = PointRapport(
            id=p["id"],
            nom=p["nom"],
            designation=p.get("designation", p["nom"]),
            groupe=p.get("groupe") or p.get("priorite", ""),
            rang=int(p.get("rang", 0)),
            lon=float(lon),
            lat=float(lat),
        )
    return points


def points_en_vigueur(insee: str) -> tuple[str | None, dict[str, PointRapport]]:
    empreinte = rapport_en_vigueur(insee)
    return empreinte, (points_du_rapport(insee, empreinte) if empreinte else {})


@dataclass(frozen=True)
class RapportEnVigueur:
    """Rapport en vigueur d'une commune pour un parcours (006) : points au rang estimé."""

    empreinte: str
    produit_le: object  # datetime de production (stockage)
    points: dict[str, PointRapport]


def rapport_pour_parcours(insee: str) -> RapportEnVigueur | None:
    """Points du rapport en vigueur et date de production ; ``None`` sans rapport (006 FR-007).
    Le rang est celui **estimé** du rapport, jamais le classement corrigé par le terrain."""
    empreinte = rapport_en_vigueur(insee)
    if empreinte is None:
        return None
    produit_le = stockage.date_rapport(insee, empreinte)
    points = points_du_rapport(insee, empreinte)
    if produit_le is None or not points:
        return None
    return RapportEnVigueur(empreinte, produit_le, points)
