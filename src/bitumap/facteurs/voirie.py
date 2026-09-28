"""Type de route et gestionnaire (FR-013) : BD TOPO recoupée avec la référence OSM.

Affiché et filtrable, **sans effet sur le score** en 002.
"""

from __future__ import annotations

import re

from bitumap.modele import Route

CLASSEMENTS = {
    "Autoroute": "autoroute",
    "Nationale": "nationale",
    "Départementale": "départementale",
    "Route intercommunale": "communale",
    "Communale": "communale",
    "Voie communale": "communale",
}
_PREFIXE_OSM = {"A": "autoroute", "N": "nationale", "D": "départementale", "C": "communale"}


def _texte(valeur) -> str | None:
    """Valeur textuelle ou ``None`` (vide, ``None`` ou NaN des tableaux pandas)."""
    if valeur is None or (isinstance(valeur, float) and valeur != valeur):
        return None
    texte = str(valeur).strip()
    return texte or None


def normaliser_numero(numero: str | None) -> str:
    """« D 9b », « D9B », « RD 9B » → « D9B »."""
    if not numero:
        return ""
    texte = re.sub(r"\s+", "", str(numero).upper())
    return re.sub(r"^R(?=[DN]\d)", "", texte)


LIBELLES = {
    "autoroute": "autoroute",
    "nationale": "nationale",
    "départementale": "départementale",
    "communale": "communale",
    "communale_presumee": "communale (présumée)",
    "privee": "voie privée",
    "indetermine": "indéterminé",
}


def libelle(classement: str) -> str:
    return LIBELLES.get(classement, classement)


def classement_osm(ref: str | None) -> str | None:
    numero = normaliser_numero((ref or "").split(";")[0])
    return _PREFIXE_OSM.get(numero[:1]) if numero[:1].isalpha() and numero[1:2].isdigit() else None


def determiner(
    classement_bdtopo: str | None,
    gestionnaire_bdtopo: str | None,
    numero_bdtopo: str | None,
    ref_osm: str | None,
    commune: str,
    troncon_trouve: bool = True,
) -> Route:
    classement_bdtopo = _texte(classement_bdtopo)
    gestionnaire_bdtopo = _texte(gestionnaire_bdtopo)
    numero_bdtopo = _texte(numero_bdtopo)
    ref_osm = _texte(ref_osm)
    ign = CLASSEMENTS.get(classement_bdtopo or "")
    osm = classement_osm(ref_osm)
    numero = normaliser_numero(numero_bdtopo) or normaliser_numero(ref_osm) or None

    if ign and osm:
        statut = "concordant" if ign == osm else "a_verifier"
        classement = ign
    elif ign:
        classement, statut = ign, "concordant"
    elif osm:
        classement, statut = osm, "a_verifier"  # OSM seul : non confirmé par l'IGN
    elif not troncon_trouve:
        return Route("indetermine", None, None, "indetermine", "aucun tronçon IGN à proximité")
    else:
        # Tronçon IGN sans classement administratif : voie communale le plus souvent.
        classement, statut = "communale_presumee", "a_verifier"

    if gestionnaire_bdtopo:
        gestionnaire = gestionnaire_bdtopo
    elif classement in ("communale", "communale_presumee"):
        gestionnaire = commune
    else:
        gestionnaire = None
    return Route(classement, gestionnaire, numero, statut, "IGN BD TOPO + OpenStreetMap")
