"""Empreinte d'un rapport (data-model.md) : clé du cache et du dossier de stockage.

Mêmes commune, méthode, versions de sources, modèle d'IA et prompt ⇒ même empreinte
⇒ même rapport (principe IV). Le modèle d'IA en fait partie (analyse F2).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import date


def empreinte(
    insee: str,
    version_methode: str,
    versions_sources: Mapping[str, date | str],
    modele_ia: str,
    version_prompt: str,
) -> str:
    sources = "|".join(
        f"{nom}:{v.isoformat() if isinstance(v, date) else v}"
        for nom, v in sorted(versions_sources.items())
    )
    texte = f"{insee}|{version_methode}|{sources}|{modele_ia}|{version_prompt}"
    return hashlib.sha256(texte.encode()).hexdigest()[:16]
