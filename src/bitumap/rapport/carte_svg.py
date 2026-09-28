"""Carte SVG du rapport (T065) : contour communal, voies bus, points ; aucune ressource externe."""

from __future__ import annotations

import math
from html import escape

from shapely.geometry import shape

from bitumap.modele import Point

LARGEUR = 1000
COULEURS = {"P1": "var(--p1)", "P2": "var(--p2)", "P3": "var(--p3)"}


class Projection:
    """Projection équirectangulaire locale (suffisante à l'échelle d'une commune)."""

    def __init__(self, minx: float, miny: float, maxx: float, maxy: float, marge: float = 20):
        self.lat0 = math.radians((miny + maxy) / 2)
        self.minx, self.maxy = minx, maxy
        largeur = (maxx - minx) * math.cos(self.lat0)
        hauteur = maxy - miny
        self.echelle = (LARGEUR - 2 * marge) / max(largeur, 1e-9)
        self.marge = marge
        self.hauteur = round(hauteur * self.echelle + 2 * marge)

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.minx) * math.cos(self.lat0) * self.echelle + self.marge
        y = (self.maxy - lat) * self.echelle + self.marge
        return round(x, 1), round(y, 1)


def _chemin(coords, proj: Projection, fermer: bool) -> str:
    pts = [proj(x, y) for x, y in coords]
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    return d + (" Z" if fermer else "")


def _forme(p: Point, x: float, y: float) -> str:
    couleur = COULEURS.get(p.priorite, "var(--p3)")
    titre = f"<title>{escape(p.nom)} — {escape(p.priorite)}, rang {p.rang}</title>"
    commun = (
        f'data-point="{escape(p.id)}" tabindex="0" role="button" class="pt" '
        f'aria-label="{escape(p.nom)}, {escape(p.priorite)}, rang {p.rang}"'
    )
    r = 7 if p.priorite == "P1" else 5
    if p.type == "feu":
        return (
            f'<rect {commun} x="{x - r}" y="{y - r}" width="{2 * r}" height="{2 * r}" '
            f'transform="rotate(45 {x} {y})" fill="{couleur}">{titre}</rect>'
        )
    if p.type == "giratoire":
        return (
            f'<circle {commun} cx="{x}" cy="{y}" r="{r + 2}" fill="none" stroke="{couleur}" '
            f'stroke-width="3">{titre}</circle>'
        )
    return f'<circle {commun} cx="{x}" cy="{y}" r="{r}" fill="{couleur}">{titre}</circle>'


def dessiner(contour: dict, voies: list[dict], points: list[Point]) -> str:
    geom = shape(contour["geometry"] if contour.get("type") == "Feature" else contour)
    proj = Projection(*geom.bounds)
    parties = []
    polygones = getattr(geom, "geoms", [geom])
    for poly in polygones:
        parties.append(f'<path d="{_chemin(poly.exterior.coords, proj, True)}" class="commune"/>')
    charge_max = max((v["charge"] for v in voies), default=1) or 1
    for v in sorted(voies, key=lambda v: v["charge"]):
        epaisseur = round(1 + 5 * v["charge"] / charge_max, 1)
        parties.append(
            f'<path d="{_chemin(v["coords"], proj, False)}" class="voie" '
            f'stroke-width="{epaisseur}"/>'
        )
    for p in sorted(points, key=lambda p: -p.rang):  # P1 dessinés en dernier (au-dessus)
        x, y = proj(p.lon, p.lat)
        parties.append(_forme(p, x, y))
    return (
        f'<svg viewBox="0 0 {LARGEUR} {proj.hauteur}" role="img" '
        f'aria-label="Carte de la commune et des points à relever" class="carte">'
        + "".join(parties)
        + "</svg>"
    )
