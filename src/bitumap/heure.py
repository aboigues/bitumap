"""Dates et heures affichées : heure de Paris (service d'Île-de-France), alors que le serveur
tourne en UTC et que la base renvoie des instants UTC. Une valeur sans fuseau est lue comme
de l'UTC."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

FUSEAU = ZoneInfo("Europe/Paris")


def locale(valeur: datetime | str) -> datetime:
    """Instant (objet ou chaîne ISO 8601) converti en heure de Paris."""
    if isinstance(valeur, str):
        valeur = datetime.fromisoformat(valeur)
    if valeur.tzinfo is None:
        valeur = valeur.replace(tzinfo=UTC)
    return valeur.astimezone(FUSEAU)


def formater(valeur: datetime | str | None, motif: str = "%d/%m/%Y %H:%M") -> str:
    """Filtre ``heure`` des gabarits : ``{{ d.cree_le|heure }}``, ``{{ x|heure("%H:%M") }}``."""
    return "" if valeur is None else locale(valeur).strftime(motif)


def aujourd_hui() -> date:
    return datetime.now(FUSEAU).date()
