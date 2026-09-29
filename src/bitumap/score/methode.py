"""Version de la méthode de score (constitution, principe IV).

Toute modification d'un facteur, d'une pondération ou d'une règle de priorité incrémente
cette version et est décrite dans ``docs/methode/CHANGELOG.md``.
"""

VERSION_METHODE = "1.2"

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
