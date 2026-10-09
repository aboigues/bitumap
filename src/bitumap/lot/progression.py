"""Avancement de la génération d'une commune en pourcentage (009, contrat §2).

Le calcul appelle ``progression(phase, fait, total)`` au fil du travail ; chaque phase occupe
une plage fixe du pourcentage, tirée des durées mesurées (research R2). L'écriture en base
est faite à chaque changement de phase et au plus toutes les 5 secondes dans une phase ;
une erreur d'écriture est journalisée sans interrompre la génération.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

journal = logging.getLogger("bitumap.lot")

# Plages du pourcentage par phase, dans l'ordre du calcul ; jamais 100 (la fin est l'état
# « terminee » de la demande).
BORNES = {"sources": (0, 5), "points": (5, 20), "ia": (20, 97), "rapport": (97, 99)}
CADENCE_S = 5.0
# Calcul final et mise en forme après les analyses par l'IA (≈ 11 s sur Paris 17e).
FIN_APRES_IA_S = 15.0


def pourcentage(phase: str, fait: int, total: int) -> int:
    if phase not in BORNES:
        raise ValueError(f"phase inconnue : {phase}")
    debut, fin = BORNES[phase]
    part = fait / total if total > 0 else 0.0
    return max(0, min(99, math.floor(debut + (fin - debut) * part)))


class Progression:
    """Fonction d'avancement passée au calcul ; ``ecrire(etape, avancement, fin_estimee)``
    enregistre l'état (``prise_en_charge.avancer``)."""

    def __init__(
        self,
        ecrire: Callable[[str, int, datetime | None], None],
        horloge: Callable[[], float] = time.monotonic,
        maintenant: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._ecrire, self._horloge, self._maintenant = ecrire, horloge, maintenant
        self._phase: str | None = None
        self._en_attente: tuple[str, int, datetime | None] | None = None
        self._ecrit_a = -math.inf
        self._debut_ia: float | None = None

    def __call__(self, phase: str, fait: int, total: int) -> None:
        etat = (phase, pourcentage(phase, fait, total), self._fin_estimee(phase, fait, total))
        maintenant = self._horloge()
        if phase != self._phase:
            if self._en_attente is not None:  # dernière valeur de la phase précédente
                self._envoyer(self._en_attente, maintenant)
            self._phase = phase
            self._envoyer(etat, maintenant)
        elif maintenant - self._ecrit_a >= CADENCE_S:
            self._envoyer(etat, maintenant)
        else:
            self._en_attente = etat

    def _fin_estimee(self, phase: str, fait: int, total: int) -> datetime | None:
        if phase != "ia":
            return None
        if self._debut_ia is None:
            self._debut_ia = self._horloge()
        if fait < 1:
            return None
        par_point = (self._horloge() - self._debut_ia) / fait
        restant = par_point * max(total - fait, 0) + FIN_APRES_IA_S
        return self._maintenant() + timedelta(seconds=restant)

    def _envoyer(self, etat: tuple[str, int, datetime | None], instant: float) -> None:
        self._en_attente = None
        self._ecrit_a = instant
        try:
            self._ecrire(*etat)
        except Exception:
            journal.exception("progression : écriture de l'avancement impossible")
