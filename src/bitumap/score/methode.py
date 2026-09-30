"""Version de la méthode de score (constitution, principe IV).

Toute modification d'un facteur, d'une pondération ou d'une règle de priorité incrémente
cette version et est décrite dans ``docs/methode/CHANGELOG.md``.
"""

from datetime import date

from bitumap.config import reglages

VERSION_METHODE = "1.2"
VERSION_METHODE_V2 = "2.0"  # 004 : en préparation, appliquée si BITUMAP_METHODE=2.0

# Mois à partir duquel l'été écoulé est complet et ses mesures publiées (température de
# surface de niveau 2, données quotidiennes) : il devient l'été de référence par défaut.
MOIS_ETE_COMPLET = 10


def version_appliquee() -> str:
    """Version de méthode des nouveaux rapports (``BITUMAP_METHODE``)."""
    return reglages().methode


def ete_reference(aujourdhui: date | None = None) -> int:
    """Été dont proviennent les indicateurs annuels (FR-007) : fixé par
    ``BITUMAP_ETE_REFERENCE``, sinon dernier été complet."""
    fixe = reglages().ete_reference
    if fixe is not None:
        return fixe
    jour = aujourdhui or date.today()
    return jour.year if jour.month >= MOIS_ETE_COMPLET else jour.year - 1


# Priorités par rang (FR-012) : P1 = 20 % premiers, P2 = 40 % suivants, P3 = reste.
PART_P1 = 0.20
PART_P2 = 0.40

# Sous-groupes du P1 (1.1) : tiers par rang, après l'âge de l'enrobé ; les premiers tiers
# reçoivent le reste de la division (31 P1 ⇒ 11, 10, 10).
SOUS_GROUPES_P1 = ("P1a", "P1b", "P1c")

# Libellés affichés (revue de la PR #17) ; les codes restent internes.
LIBELLES_GROUPES = {
    "P1a": "Critique",
    "P1b": "Sérieux",
    "P1c": "Important",
    "P2": "À surveiller",
    "P3": "Supportable",
}
