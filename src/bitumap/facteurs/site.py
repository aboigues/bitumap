"""Site : pente, revêtement rigide, ouvrage d'art (méthode 1.0)."""

from __future__ import annotations

from bitumap.modele import Facteur

SEUIL_PENTE = 3.0
PENTE_DOUTEUSE = 9.0
EFFET_PENTE_MAX = 1.32
EFFET_RIGIDE = 0.5


def effet_pente(pente: float) -> float:
    """1,0 sous 3 % ; puis +8 % par point de pente au-delà de 2 %, plafonné à ×1,32."""
    if pente < SEUIL_PENTE:
        return 1.0
    return min(EFFET_PENTE_MAX, 1.0 + 0.08 * (pente - 2.0))


def pente(p: float | None) -> Facteur:
    if p is None:
        return Facteur("pente", None, 1.0, statut="non_evalue", explication="Pente non évaluée")
    if p > PENTE_DOUTEUSE:
        return Facteur(
            "pente",
            round(p, 1),
            1.0,
            statut="non_evalue",
            explication=f"Pente mesurée {p:.1f} % douteuse (dalle / ouvrage), non prise en compte",
            unite="%",
        )
    effet = effet_pente(p)
    return Facteur(
        "pente",
        round(p, 1),
        effet,
        explication=f"Pente {p:.1f} %" if effet > 1 else f"Pente faible ({p:.1f} %)",
        unite="%",
        visible=effet > 1,
    )


def revetement(surface: str, rigide: bool) -> Facteur:
    if rigide:
        return Facteur(
            "revetement",
            surface,
            EFFET_RIGIDE,
            explication=f"Revêtement rigide ({surface}) : peu sensible à l'orniérage",
        )
    return Facteur(
        "revetement",
        surface or "asphalt",
        1.0,
        explication="Enrobé bitumineux",
        visible=False,
        provenance="estime" if not surface else "mesure",
    )


def ouvrage(pont: bool) -> Facteur | None:
    if not pont:
        return None
    return Facteur(
        "ouvrage_art", True, 1.0, explication="Sur ouvrage d'art (vérifier l'étanchéité)"
    )
