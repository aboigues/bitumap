"""Îlot de chaleur : aléa de jour de l'Institut Paris Region (0 à 16) → ×0,92 à ×1,08."""

from __future__ import annotations

import numpy as np

from bitumap.modele import Facteur

SEUIL_MARQUE = 11


def effet_alea(alea: float) -> float:
    return 0.92 + 0.16 * max(0.0, min(16.0, alea)) / 16


def calculer(alea: float | None, lcz: str | None) -> Facteur:
    if alea is None or alea < 0:
        return Facteur(
            "chaleur", None, 1.0, statut="non_evalue", explication="Îlot de chaleur non évalué"
        )
    marque = alea >= SEUIL_MARQUE
    return Facteur(
        "chaleur",
        int(alea),
        effet_alea(alea),
        explication=f"Îlot de chaleur marqué (aléa jour {int(alea)}/16)"
        if marque
        else f"Aléa de chaleur de jour {int(alea)}/16"
        + (f", zone climatique {lcz}" if lcz else ""),
        unite="/16",
        visible=marque,
    )


# --- Méthode 2.0 (004 US2, FR-005, FR-006) : indicateurs candidats, évalués un par un. -----
# Un indicateur n'agit sur le score que s'il figure dans ``INDICATEURS_CHALEUR_RETENUS``
# (``score.methode``), après validation sur les relevés (R7) ; sinon il est affiché, avec
# l'effet qu'il aurait (``details.effet_si_retenu``), et son effet est 1,0. Bornes fixées
# d'avance, de même amplitude que l'aléa de la 1.2 (×0,92 à ×1,08), recalibrées sur les
# relevés.

ALEA = "chaleur_alea"
TEMPERATURE = "chaleur_temperature_surface"
MINERALISATION = "chaleur_mineralisation"
CONTEXTE = "chaleur_contexte_urbain"
CANDIDATS = (ALEA, TEMPERATURE, MINERALISATION, CONTEXTE)

EFFET_MIN, EFFET_MAX = 0.92, 1.08
TEMPERATURE_FRAICHE_C, TEMPERATURE_CHAUDE_C = 28.0, 38.0
RAYON_MINERALISATION_M = 50

# Zones climatiques locales (Stewart et Oke ; classe principale, avant le point) :
# bâti compact, industrie lourde, sols imperméables ⇒ plus chaud ; arbres, végétation basse,
# sol nu, eau ⇒ plus frais ; bâti ouvert ⇒ neutre.
LCZ_CHAUDES = {"1", "2", "3", "8", "10", "E"}
LCZ_FRAICHES = {"A", "B", "C", "D", "F", "G"}
LIBELLES_LCZ = {
    "1": "bâti compact de grande hauteur",
    "2": "bâti compact de hauteur moyenne",
    "3": "bâti compact bas",
    "4": "bâti ouvert de grande hauteur",
    "5": "bâti ouvert de hauteur moyenne",
    "6": "bâti ouvert bas",
    "7": "bâti léger bas",
    "8": "grands bâtiments bas",
    "9": "bâti épars",
    "10": "industrie lourde",
    "A": "arbres denses",
    "B": "arbres épars",
    "C": "buissons",
    "D": "végétation basse",
    "E": "sol imperméable",
    "F": "sol nu",
    "G": "eau",
}


def _interpoler(valeur: float, bas: float, haut: float) -> float:
    t = max(0.0, min(1.0, (valeur - bas) / (haut - bas)))
    return EFFET_MIN + (EFFET_MAX - EFFET_MIN) * t


def effet_temperature(celsius: float) -> float:
    return _interpoler(celsius, TEMPERATURE_FRAICHE_C, TEMPERATURE_CHAUDE_C)


def effet_mineralisation(pourcent: float) -> float:
    return _interpoler(pourcent, 0.0, 100.0)


def classe_lcz(lcz) -> str | None:
    if lcz is None or lcz != lcz or not str(lcz).strip():
        return None
    return str(lcz).split(".")[0].strip().upper() or None


def effet_contexte(classe: str) -> float:
    if classe in LCZ_CHAUDES:
        return EFFET_MAX
    if classe in LCZ_FRAICHES:
        return EFFET_MIN
    return 1.0


def mineralisation(vegetation, resolution_m: float = 1.0) -> float | None:
    """Part (%) des surfaces non végétales à moins de ``RAYON_MINERALISATION_M`` du centre
    du masque de végétation (infrarouge, centré sur le point)."""
    if vegetation is None:
        return None
    lignes, colonnes = np.indices(vegetation.shape)
    cy, cx = (vegetation.shape[0] - 1) / 2, (vegetation.shape[1] - 1) / 2
    disque = ((lignes - cy) ** 2 + (colonnes - cx) ** 2) * resolution_m**2 <= (
        RAYON_MINERALISATION_M**2
    )
    return float(100 * (1 - vegetation[disque].mean()))


def _candidat(nom, valeur, effet, unite, explication, retenus, details=None) -> Facteur:
    if valeur is None:
        return Facteur(
            nom,
            None,
            1.0,
            statut="non_evalue",
            explication=f"{explication} : non évalué (donnée absente)",
            unite=unite,
            visible=False,
            details=details or {},
        )
    retenu = nom in retenus
    return Facteur(
        nom,
        valeur,
        effet if retenu else 1.0,
        explication=explication if retenu else f"{explication} — non retenu (apport non démontré)",
        unite=unite,
        visible=retenu and effet > 1.0,
        details={**(details or {}), "retenu": retenu, "effet_si_retenu": round(effet, 4)},
    )


def candidats(
    alea: float | None,
    lcz,
    temperature_c: float | None,
    mineralisation_pct: float | None,
    ete_temperature: int | None,
    retenus: tuple[str, ...] | frozenset[str],
) -> list[Facteur]:
    """Les quatre indicateurs de chaleur d'un point, en méthode 2.0."""
    alea = None if alea is None or alea < 0 else alea
    classe = classe_lcz(lcz)
    return [
        _candidat(
            ALEA,
            None if alea is None else int(alea),
            effet_alea(alea) if alea is not None else 1.0,
            "/16",
            "Aléa de chaleur de jour (Institut Paris Region 2022)"
            + (f" : {int(alea)}/16" if alea is not None else ""),
            retenus,
        ),
        _candidat(
            TEMPERATURE,
            None if temperature_c is None else round(temperature_c, 1),
            effet_temperature(temperature_c) if temperature_c is not None else 1.0,
            "°C",
            "Température de surface"
            + (
                f" l'été {ete_temperature} : {temperature_c:.1f} °C (médiane, Landsat)"
                if temperature_c is not None
                else ""
            ),
            retenus,
            {"ete": ete_temperature} if temperature_c is not None else None,
        ),
        _candidat(
            MINERALISATION,
            None if mineralisation_pct is None else round(mineralisation_pct),
            effet_mineralisation(mineralisation_pct) if mineralisation_pct is not None else 1.0,
            "%",
            "Surfaces minérales à moins de 50 m"
            + (f" : {mineralisation_pct:.0f} %" if mineralisation_pct is not None else ""),
            retenus,
        ),
        _candidat(
            CONTEXTE,
            classe,
            effet_contexte(classe) if classe is not None else 1.0,
            "",
            "Contexte urbain"
            + (f" : {LIBELLES_LCZ.get(classe, classe)} (zone {classe})" if classe else ""),
            retenus,
        ),
    ]
