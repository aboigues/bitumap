"""Versions courantes des sources (table ``source_version``) et empreinte d'un rapport.

Seules les sources **versionnées** entrent dans l'empreinte : IDFM (date de mise à jour du jeu),
OSM (date de l'extrait Geofabrik), îlots de chaleur (millésime 2022). Les sources interrogées en
direct sans version (BD TOPO, altimétrie, orthophotos, Panoramax) ont leur date inscrite dans
le rapport ; la validité de 30 jours d'un rapport borne leur ancienneté (FR-008).
"""

from __future__ import annotations

from datetime import date

from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.lot.empreinte import empreinte
from bitumap.score.methode import VERSION_METHODE, ete_reference, version_appliquee

SOURCES_VERSIONNEES = ("idfm", "osm", "chaleur")
VERSION_CHALEUR = date(2022, 1, 1)


def enregistrer(source: str, date_extraction: date, portee: str = "regionale") -> None:
    with connexion() as conn:
        conn.execute(
            "INSERT INTO source_version (source, portee, date_extraction) VALUES (%s, %s, %s)"
            " ON CONFLICT (source, portee) DO UPDATE"
            " SET date_extraction = excluded.date_extraction, rafraichie_le = now()",
            (source, portee, date_extraction),
        )


def courantes() -> dict[str, date]:
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT source, date_extraction FROM source_version WHERE portee = 'regionale'"
        ).fetchall()
    return {ligne["source"]: ligne["date_extraction"] for ligne in lignes}


def rafraichies_aujourdhui() -> bool:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT count(*) AS n FROM source_version"
            " WHERE portee = 'regionale' AND rafraichie_le::date = current_date"
        ).fetchone()
    return ligne["n"] >= len(SOURCES_VERSIONNEES)


def empreinte_courante(insee: str) -> str:
    """Empreinte d'un rapport qui serait produit maintenant pour cette commune."""
    return empreinte_pour(insee, {s: v for s, v in courantes().items() if s in SOURCES_VERSIONNEES})


def empreinte_pour(insee: str, versions_sources: dict[str, date]) -> str:
    """Empreinte selon la méthode appliquée ; en 2.0, l'été de référence y entre : un nouvel
    été rend les rapports précédents non réutilisables (004 FR-007, R8)."""
    r = reglages()
    version = version_appliquee()
    sources: dict[str, date | str] = dict(versions_sources)
    if version != VERSION_METHODE:
        sources["ete_reference"] = str(ete_reference())
    return empreinte(insee, version, sources, r.ia_modele, r.ia_version_prompt)
