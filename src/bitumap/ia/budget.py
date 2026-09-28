"""Budget de l'IA (FR-024, FR-029) : réservation avant chaque appel, ajustement après.

Plafonds : par rapport (2 €) et par jour (20 €) ; au-delà, aucun appel. Seuil d'alerte
mensuel (5 €) : un e-mail au mainteneur, une seule fois par mois, sans blocage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from bitumap import courriel
from bitumap.config import reglages
from bitumap.db import connexion

JETONS_PAR_IMAGE_MAX = 400  # 512 px ≈ 361 jetons (Mistral) ; marge prudente
JETONS_CONSIGNE = 700


def cout(jetons_entree: int, jetons_sortie: int) -> Decimal:
    r = reglages()
    return (
        Decimal(jetons_entree) * r.ia_tarif_entree_eur_mtok
        + Decimal(jetons_sortie) * r.ia_tarif_sortie_eur_mtok
    ) / Decimal(1_000_000)


def estimation(nb_images: int, jetons_sortie_max: int) -> Decimal:
    return cout(nb_images * JETONS_PAR_IMAGE_MAX + JETONS_CONSIGNE, jetons_sortie_max)


class BudgetRapport:
    """Suivi du coût d'un rapport ; toute réservation vérifie aussi le plafond du jour."""

    def __init__(self) -> None:
        self.depense = Decimal(0)

    def reserver(self, montant: Decimal) -> bool:
        r = reglages()
        if self.depense + montant > r.ia_plafond_rapport_eur:
            return False
        with connexion() as conn:
            ligne = conn.execute(
                "INSERT INTO cout_ia_jour (jour, montant_eur) VALUES (current_date, %s)"
                " ON CONFLICT (jour) DO UPDATE SET montant_eur = cout_ia_jour.montant_eur + %s"
                " WHERE cout_ia_jour.montant_eur + %s <= %s"
                " RETURNING montant_eur",
                (montant, montant, montant, r.ia_plafond_jour_eur),
            ).fetchone()
        if ligne is None or ligne["montant_eur"] > r.ia_plafond_jour_eur:
            return False
        self.depense += montant
        return True

    def ajuster(self, reserve: Decimal, reel: Decimal) -> None:
        difference = reel - reserve
        self.depense += difference
        with connexion() as conn:
            conn.execute(
                "UPDATE cout_ia_jour SET montant_eur = greatest(0, montant_eur + %s)"
                " WHERE jour = current_date",
                (difference,),
            )
        verifier_alerte_mensuelle()


def budget_jour_epuise() -> bool:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT montant_eur FROM cout_ia_jour WHERE jour = current_date"
        ).fetchone()
    return ligne is not None and ligne["montant_eur"] >= reglages().ia_plafond_jour_eur


def cout_du_mois() -> Decimal:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT coalesce(sum(montant_eur), 0) AS total FROM cout_ia_jour"
            " WHERE date_trunc('month', jour) = date_trunc('month', current_date)"
        ).fetchone()
    return Decimal(ligne["total"])


def verifier_alerte_mensuelle() -> bool:
    """Envoie l'alerte mensuelle une seule fois quand le seuil est franchi (FR-029)."""
    seuil = reglages().alerte_mensuelle_eur
    total = cout_du_mois()
    if total < seuil:
        return False
    cle = f"cout_mensuel_ia:{datetime.now(UTC):%Y-%m}"
    with connexion() as conn:
        nouvelle = conn.execute(
            "INSERT INTO alerte_envoyee (cle) VALUES (%s) ON CONFLICT DO NOTHING RETURNING cle",
            (cle,),
        ).fetchone()
    if nouvelle is None:
        return False
    courriel.envoyer(
        courriel.alerte_mainteneur(
            f"coût IA du mois : {total:.2f} € (seuil {seuil} €)",
            "Le coût de l'IA vision a atteint le seuil d'alerte mensuel. Aucun blocage : les"
            " plafonds par rapport et par jour restent les seules limites.",
        )
    )
    return True
