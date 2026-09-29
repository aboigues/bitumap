"""Journal de génération ``journal.json`` (contracts/report-bundle.md ; FR-023) et journal
structuré du service (une ligne JSON par événement, lisible et filtrable dans Cockpit).

Aucune donnée personnelle : ni adresse e-mail, ni identifiant de compte.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

CHAMPS_LOGGING = set(vars(logging.makeLogRecord({})))


class FormatJson(logging.Formatter):
    """Une ligne JSON par enregistrement : horodatage, niveau, source, message et champs
    passés en ``extra`` (par ``evenement``) ; trace d'exception le cas échéant."""

    def format(self, record: logging.LogRecord) -> str:
        ligne = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "niveau": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        }
        ligne |= {k: v for k, v in vars(record).items() if k not in CHAMPS_LOGGING}
        if record.exc_info:
            ligne["exception"] = self.formatException(record.exc_info)
        return json.dumps(ligne, ensure_ascii=False, default=str)


def configurer_journalisation(niveau: int = logging.INFO) -> None:
    gestionnaire = logging.StreamHandler()
    gestionnaire.setFormatter(FormatJson())
    logging.basicConfig(level=niveau, handlers=[gestionnaire], force=True)


def evenement(journal: logging.Logger, nom: str, niveau: int = logging.INFO, **champs) -> None:
    """Événement structuré : ``nom`` en message, ``champs`` en attributs JSON."""
    journal.log(niveau, nom, extra={"evenement": nom, **champs})


@dataclass
class StatistiquesIA:
    modele: str = ""
    version_prompt: str = ""
    appels: int = 0
    succes_cache: int = 0
    jetons_entree: int = 0
    jetons_sortie: int = 0
    cout_eur: Decimal = Decimal(0)
    non_evalues: int = 0


@dataclass
class JournalGeneration:
    insee: str
    version_methode: str
    lot_id: str | None = None
    debut: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    fin: str | None = None
    durees_s: dict[str, float] = field(default_factory=dict)
    nb_points: int = 0
    ia: StatistiquesIA = field(default_factory=StatistiquesIA)
    avertissements: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    def chronometrer(self, etape: str):
        return _Chrono(self, etape)

    def terminer(self) -> None:
        self.fin = datetime.now(UTC).isoformat()

    def en_json(self) -> bytes:
        return json.dumps(asdict(self), default=str, ensure_ascii=False, indent=2).encode()


class _Chrono:
    def __init__(self, journal: JournalGeneration, etape: str):
        self.journal, self.etape = journal, etape

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.journal.durees_s[self.etape] = round(time.perf_counter() - self.t0, 3)
        return False
