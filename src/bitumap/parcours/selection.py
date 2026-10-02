"""Sélection des points dans la durée maximale (006 R3, FR-005, FR-006, SC-003).

Les candidats sont pris **dans l'ordre du rang** (les plus critiques d'abord), sans
réordonnancement. Pour chacun : trajet depuis le dernier point retenu, arrêt, retour au
départ ; retenu si le total tient dans la durée maximale, sinon « non visité » et candidat
suivant. Économie d'appels : borne inférieure à vol d'oiseau (aucun appel pour un candidat
qui ne tiendrait même pas en ligne droite à la vitesse maximale du mode), arrêt quand le
reste est inférieur au temps d'arrêt, 60 candidats évalués au plus.

``duree(a, b) -> (secondes, mètres)`` est injectée (itinéraire réel ou simulé).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from bitumap.parcours.itineraire import Inaccessible, Position

MAX_CANDIDATS = 60
# Vitesse maximale par mode pour la borne à vol d'oiseau : une valeur trop basse écarterait
# des points atteignables par voie rapide (130 km/h en voiture) ; 6 km/h à pied.
VITESSE_MAX_KMH = {"voiture": 130.0, "pied": 6.0}
RAYON_TERRE_M = 6_371_000

Duree = Callable[[Position, Position], tuple[float, float]]


class AucunPoint(Exception):
    pass


class DureeInsuffisante(Exception):
    def __init__(self, duree_min_s: float):
        super().__init__(duree_min_s)
        self.duree_min_s = duree_min_s


@dataclass(frozen=True)
class Candidat:
    point_id: str
    rang: int
    niveau: str
    designation: str
    lon: float
    lat: float

    @property
    def position(self) -> Position:
        return (self.lon, self.lat)


@dataclass
class Visite:
    ordre: int
    point_id: str
    rang: int
    niveau: str
    designation: str
    lon: float
    lat: float
    duree_cumulee_s: float
    distance_cumulee_m: float
    accessible: bool = True


@dataclass
class NonVisite:
    point_id: str
    rang: int
    niveau: str
    raison: str  # duree, inaccessible, releve_recent, limite_candidats


@dataclass
class Selection:
    visites: list[Visite] = field(default_factory=list)
    non_visites: list[NonVisite] = field(default_factory=list)
    duree_totale_s: float = 0.0  # trajets, arrêts et retour
    distance_totale_m: float = 0.0
    duree_restante_s: float = 0.0


def vol_oiseau_m(a: Position, b: Position) -> float:
    """Distance orthodromique (haversine) entre deux positions (lon, lat)."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * RAYON_TERRE_M * math.asin(math.sqrt(h))


def selectionner(
    depart: Position,
    candidats: list[Candidat],
    mode: str,
    duree_max_s: float,
    arret_s: float,
    duree: Duree,
    max_candidats: int = MAX_CANDIDATS,
) -> Selection:
    if not candidats:
        raise AucunPoint
    vitesse = VITESSE_MAX_KMH[mode] / 3.6
    s = Selection()
    courant, cumul_s, cumul_m = depart, 0.0, 0.0
    retour: tuple[float, float] = (0.0, 0.0)  # retour au départ depuis le dernier retenu
    retours: dict[Position, tuple[float, float]] = {}

    def non_visite(c: Candidat, raison: str) -> None:
        s.non_visites.append(NonVisite(c.point_id, c.rang, c.niveau, raison))

    for i, c in enumerate(sorted(candidats, key=lambda c: c.rang)):
        if i >= max_candidats:
            non_visite(c, "limite_candidats")
            continue
        reste = duree_max_s - cumul_s
        borne = (vol_oiseau_m(courant, c.position) + vol_oiseau_m(c.position, depart)) / vitesse
        if reste < arret_s or borne + arret_s > reste:
            non_visite(c, "duree")
            continue
        try:
            aller = duree(courant, c.position)
            if c.position not in retours:
                retours[c.position] = duree(c.position, depart)
        except Inaccessible:
            non_visite(c, "inaccessible")
            continue
        if aller[0] + arret_s + retours[c.position][0] > reste:
            non_visite(c, "duree")
            continue
        cumul_s += aller[0] + arret_s
        cumul_m += aller[1]
        retour = retours[c.position]
        s.visites.append(
            Visite(
                len(s.visites) + 1,
                c.point_id,
                c.rang,
                c.niveau,
                c.designation,
                c.lon,
                c.lat,
                cumul_s,
                cumul_m,
            )
        )
        courant = c.position
    if not s.visites:
        raise DureeInsuffisante(_duree_minimale(depart, candidats, arret_s, duree))
    s.duree_totale_s = cumul_s + retour[0]
    s.distance_totale_m = cumul_m + retour[1]
    s.duree_restante_s = duree_max_s - s.duree_totale_s
    return s


def _duree_minimale(depart, candidats, arret_s, duree) -> float:
    """Durée nécessaire pour visiter le premier point accessible (aller, arrêt, retour)."""
    for c in sorted(candidats, key=lambda c: c.rang):
        try:
            return duree(depart, c.position)[0] + arret_s + duree(c.position, depart)[0]
        except Inaccessible:
            continue
    return 0.0
