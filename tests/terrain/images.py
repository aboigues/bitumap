"""Images de test générées (aucune photo réelle, T004) : JPEG avec métadonnées EXIF
(position, appareil, auteur, date), PNG, faux JPEG (texte) et fichier trop lourd."""

from __future__ import annotations

import io

from PIL import Image

EXIF_MODELE, EXIF_AUTEUR, EXIF_DATE, EXIF_GPS = 0x0110, 0x013B, 0x0132, 0x8825


def jpeg_avec_exif(largeur: int = 800, hauteur: int = 600) -> bytes:
    image = Image.new("RGB", (largeur, hauteur), (90, 90, 95))
    exif = Image.Exif()
    exif[EXIF_MODELE] = "Téléphone de test"
    exif[EXIF_AUTEUR] = "Agent Dupont"
    exif[EXIF_DATE] = "2026:09:29 10:15:00"
    exif[EXIF_GPS] = {1: "N", 2: (48.0, 54.0, 3.0), 3: "E", 4: (2.0, 15.0, 36.0)}
    tampon = io.BytesIO()
    image.save(tampon, format="JPEG", exif=exif)
    return tampon.getvalue()


def png() -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (320, 240), (120, 60, 40)).save(tampon, format="PNG")
    return tampon.getvalue()


def faux_jpeg() -> bytes:
    return b"ceci n'est pas une image, malgre l'extension .jpg\n" * 20


def trop_lourd(octets: int) -> bytes:
    return b"\xff\xd8" + b"\x00" * octets


def metadonnees(contenu: bytes) -> dict:
    """Métadonnées EXIF d'une image (vide si aucune)."""
    return dict(Image.open(io.BytesIO(contenu)).getexif())
