"""Version de la méthode de score (constitution, principe IV).

Toute modification d'un facteur, d'une pondération ou d'une règle de priorité incrémente
cette version et est décrite dans ``docs/methode/CHANGELOG.md``.
"""

VERSION_METHODE = "1.0"

# Priorités par rang (FR-012) : P1 = 20 % premiers, P2 = 40 % suivants, P3 = reste.
PART_P1 = 0.20
PART_P2 = 0.40
