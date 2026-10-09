#!/usr/bin/env python3
"""Génère l'icône du site (issue #56) : ``favicon.svg`` et ``favicon.ico``.

Carré couleur asphalte, deux ornières ambre en perspective (une voie vue de face, pas deux
barres verticales qui se liraient « pause »), couleurs de ``style.css`` (thème sombre).
Lancé à la main après une modification du dessin ; les fichiers produits sont versionnés.

Usage : ``uv run python tools/favicon.py``
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIQUE = Path(__file__).resolve().parents[1] / "src" / "bitumap" / "api" / "statique"

COTE = 64
FOND = "#1e2328"  # --surface du thème sombre
BANDE = "#ebb33a"  # --accent du thème sombre
RAYON = 12
HAUT, BAS = 12, 54
# Sommets de chaque ornière (trapèze qui se resserre vers le haut), sens horaire.
ORNIERES = (
    ((24, HAUT), (29, HAUT), (22, BAS), (9, BAS)),
    ((35, HAUT), (40, HAUT), (55, BAS), (42, BAS)),
)

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {COTE} {COTE}">
<rect width="{COTE}" height="{COTE}" rx="{RAYON}" fill="{FOND}"/>
{
    "".join(
        f'<polygon points="{" ".join(f"{x},{y}" for x, y in sommets)}" fill="{BANDE}"/>\n'
        for sommets in ORNIERES
    )
}</svg>
"""


def dessiner(cote: int = 256) -> Image.Image:
    """Même dessin que le SVG, tracé en grand puis réduit (bords lissés)."""
    k = cote / COTE
    image = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    trait = ImageDraw.Draw(image)
    trait.rounded_rectangle((0, 0, cote - 1, cote - 1), radius=RAYON * k, fill=FOND)
    for sommets in ORNIERES:
        trait.polygon([(x * k, y * k) for x, y in sommets], fill=BANDE)
    return image


def main() -> None:
    (STATIQUE / "favicon.svg").write_text(SVG)
    dessiner().save(STATIQUE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"Écrits : {STATIQUE / 'favicon.svg'}, {STATIQUE / 'favicon.ico'}")


if __name__ == "__main__":
    main()
