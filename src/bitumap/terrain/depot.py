"""Relevés terrain en base (003 : data-model.md, contracts/http-api.md).

Un relevé est créé avec un identifiant fourni par le téléphone : l'envoi est idempotent
(R3). Rien n'est modifié en place : toute correction ajoute une version (FR-011).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import psycopg
from pydantic import BaseModel, Field, model_validator

from bitumap.api import quotas
from bitumap.api.application import ErreurPublique
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.terrain.points import points_en_vigueur
from bitumap.terrain.pseudonyme import pseudonyme

Niveau = Literal["absent", "leger", "marque", "grave"]
SourceRefection = Literal["constatee", "services_techniques", "estimee_agent"]
DISTANCE_ELOIGNEE_M = 100
LIBELLES_NIVEAUX = {"absent": "absent", "leger": "léger", "marque": "marqué", "grave": "grave"}
LIBELLES_SOURCES = {
    "constatee": "constatée",
    "services_techniques": "services techniques",
    "estimee_agent": "estimée par l'agent",
}


class Constat(BaseModel):
    """Contenu d'une version de relevé ; bornes de data-model.md."""

    niveau: Niveau
    profondeur_mm: int | None = Field(default=None, ge=0, le=200)
    instrument: str | None = Field(default=None, max_length=100)
    observation: str | None = Field(default=None, max_length=1000)
    annee_refection: int | None = Field(default=None, ge=1950)
    source_refection: SourceRefection | None = None
    confirme_malgre_incoherence: bool = False

    @model_validator(mode="after")
    def _coherence_des_champs(self):
        if self.annee_refection is not None and self.annee_refection > datetime.now(UTC).year:
            raise ValueError("année de réfection dans le futur")
        if self.profondeur_mm is not None and not (self.instrument or "").strip():
            raise ValueError("instrument requis avec une profondeur")
        if self.annee_refection is not None and self.source_refection is None:
            raise ValueError("source requise avec une année de réfection")
        return self


class SaisieReleve(Constat):
    commune_insee: str = Field(pattern=r"^\d{5}$")
    point_id: str = Field(pattern=r"^[A-Z][0-9]{1,20}$")
    cree_le: datetime
    lon: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)

    @model_validator(mode="after")
    def _date_plausible(self):
        maintenant = datetime.now(UTC)
        cree_le = self.cree_le if self.cree_le.tzinfo else self.cree_le.replace(tzinfo=UTC)
        if not maintenant - timedelta(days=365) <= cree_le <= maintenant + timedelta(minutes=10):
            raise ValueError("date de saisie invalide")
        if (self.lon is None) != (self.lat is None):
            raise ValueError("position incomplète")
        return self


def niveau_selon_profondeur(profondeur_mm: int) -> Niveau:
    """Repères de FR-005b : léger < 10 mm, marqué 10–20 mm, grave > 20 mm."""
    if profondeur_mm < 10:
        return "leger"
    return "marque" if profondeur_mm <= 20 else "grave"


def incoherence(niveau: str, profondeur_mm: int | None) -> Niveau | None:
    """Niveau suggéré quand la profondeur contredit le niveau choisi (R11), sinon ``None``."""
    if profondeur_mm is None:
        return None
    suggere = niveau_selon_profondeur(profondeur_mm)
    if niveau == "absent":
        return suggere if profondeur_mm >= 10 else None
    return suggere if suggere != niveau else None


def _distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    dx = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


@dataclass
class Resultat:
    statut: int  # 200 (déjà enregistré ou avertissement), 201 (créé)
    corps: dict


def _avertissement(constat: Constat) -> Resultat | None:
    suggere = incoherence(constat.niveau, constat.profondeur_mm)
    if suggere and not constat.confirme_malgre_incoherence:
        return Resultat(
            200,
            {
                "avertissement": "mesure_incoherente",
                "niveau_suggere": suggere,
                "message": (
                    f"{constat.profondeur_mm} mm correspond au niveau "
                    f"« {LIBELLES_NIVEAUX[suggere]} » : corrigez ou confirmez votre choix."
                ),
            },
        )
    return None


def _inserer_version(conn, releve_id: str, version: int, constat: Constat) -> None:
    conn.execute(
        "INSERT INTO releve_version (releve_id, version, niveau, profondeur_mm, instrument,"
        " observation, annee_refection, source_refection, incoherence_confirmee)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            releve_id,
            version,
            constat.niveau,
            constat.profondeur_mm,
            (constat.instrument or "").strip() or None,
            (constat.observation or "").strip() or None,
            constat.annee_refection,
            constat.source_refection,
            incoherence(constat.niveau, constat.profondeur_mm) is not None,
        ),
    )


def creer(compte_id: str, releve_id: str, saisie: SaisieReleve) -> Resultat:
    with connexion() as conn:
        existant = conn.execute(
            "SELECT compte_id FROM releve WHERE id = %s", (releve_id,)
        ).fetchone()
    if existant is not None:
        if str(existant["compte_id"]) != str(compte_id):
            raise ErreurPublique(409, "identifiant_pris", "Identifiant de relevé déjà utilisé.")
        return Resultat(200, {"id": releve_id, "deja_enregistre": True})

    _, points = points_en_vigueur(saisie.commune_insee)
    point = points.get(saisie.point_id)
    if point is None:
        raise ErreurPublique(404, "point_inconnu", "Ce point n'existe pas dans le rapport.")
    if (avertissement := _avertissement(saisie)) is not None:
        return avertissement

    distance = (
        round(_distance_m(saisie.lon, saisie.lat, point.lon, point.lat), 1)
        if saisie.lon is not None
        else None
    )
    with connexion() as conn:
        if not quotas.consommer(
            conn,
            f"releve:compte:{compte_id}",
            quotas.JOUR,
            reglages().quota_releves_compte_jour,
        ):
            raise ErreurPublique(
                429, "quota_releves", "Limite de relevés du jour atteinte : réessayez demain."
            )
        conn.execute(
            "INSERT INTO releve (id, commune_insee, point_id, point_nom, point_designation,"
            " niveau_estime, compte_id, cree_le, lon, lat, distance_point_m)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                releve_id,
                saisie.commune_insee,
                point.id,
                point.nom,
                point.designation,
                point.groupe,
                compte_id,
                saisie.cree_le,
                saisie.lon,
                saisie.lat,
                distance,
            ),
        )
        _inserer_version(conn, releve_id, 1, saisie)
    return Resultat(
        201,
        {
            "id": releve_id,
            "version": 1,
            "position_eloignee": distance is not None and distance > DISTANCE_ELOIGNEE_M,
        },
    )


class Correction(Constat):
    """Nouvelle version d'un relevé ; ``version`` (facultatif) rend le réenvoi idempotent."""

    version: int | None = Field(default=None, ge=2)


_CHAMPS_CONSTAT = (
    "niveau",
    "profondeur_mm",
    "instrument",
    "observation",
    "annee_refection",
    "source_refection",
)


def _releve_modifiable(conn, releve_id: str, compte_id: str) -> None:
    ligne = conn.execute(
        "SELECT compte_id FROM releve WHERE id = %s AND retire_le IS NULL", (releve_id,)
    ).fetchone()
    if ligne is None:
        raise ErreurPublique(404, "releve_inconnu", "Relevé introuvable.")
    if str(ligne["compte_id"]) != str(compte_id):
        raise ErreurPublique(403, "pas_auteur", "Seul l'auteur peut modifier ce relevé.")


def corriger(compte_id: str, releve_id: str, correction: Correction) -> Resultat:
    """Ajoute une version (FR-011) : rien n'est modifié en place. Réenvoi de la même version
    avec le même contenu ⇒ ``200`` ; version déjà prise ou non consécutive ⇒ ``409``."""
    with connexion() as conn:
        _releve_modifiable(conn, releve_id, compte_id)
        derniere = conn.execute(
            "SELECT * FROM releve_version WHERE releve_id = %s ORDER BY version DESC LIMIT 1",
            (releve_id,),
        ).fetchone()
        if correction.version is not None and correction.version <= derniere["version"]:
            existante = conn.execute(
                "SELECT * FROM releve_version WHERE releve_id = %s AND version = %s",
                (releve_id, correction.version),
            ).fetchone()
            propre = Correction.model_validate(
                {k: existante[k] for k in _CHAMPS_CONSTAT} | {"version": correction.version}
            )
            if all(getattr(propre, k) == getattr(correction, k) for k in _CHAMPS_CONSTAT):
                return Resultat(
                    200, {"id": releve_id, "version": correction.version, "deja_enregistre": True}
                )
        numero = derniere["version"] + 1
        if correction.version is not None and correction.version != numero:
            raise ErreurPublique(
                409, "version_prise", "Ce relevé a changé entre-temps : rechargez la page."
            )
        if (avertissement := _avertissement(correction)) is not None:
            return avertissement
        try:
            _inserer_version(conn, releve_id, numero, correction)
        except psycopg.errors.UniqueViolation as erreur:  # correction concurrente
            raise ErreurPublique(
                409, "version_prise", "Ce relevé a changé entre-temps : rechargez la page."
            ) from erreur
    return Resultat(201, {"id": releve_id, "version": numero})


def retirer(releve_id: str, compte_id: str, motif: str | None, mainteneur: bool = False) -> None:
    """Retrait d'un relevé : masqué partout, trace conservée (qui, quand, motif ; R12).
    L'auteur ou le mainteneur ; un retrait rejoué est sans effet."""
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT compte_id, retire_le FROM releve WHERE id = %s", (releve_id,)
        ).fetchone()
        if ligne is None:
            raise ErreurPublique(404, "releve_inconnu", "Relevé introuvable.")
        if not mainteneur and str(ligne["compte_id"]) != str(compte_id):
            raise ErreurPublique(403, "pas_auteur", "Seul l'auteur peut retirer ce relevé.")
        if ligne["retire_le"] is not None:
            return
        conn.execute(
            "UPDATE releve SET retire_le = now(), retire_par = %s, motif_retrait = %s"
            " WHERE id = %s",
            (compte_id, _motif(motif, mainteneur), releve_id),
        )


def _motif(motif: str | None, mainteneur: bool) -> str:
    texte = (motif or "").strip()[:200]
    return texte or ("RGPD" if mainteneur else "erreur")


def auteur_de(releve_id: str) -> tuple[bool, str | None]:
    """(existe, compte_id de l'auteur)."""
    with connexion() as conn:
        ligne = conn.execute("SELECT compte_id FROM releve WHERE id = %s", (releve_id,)).fetchone()
    if ligne is None:
        return False, None
    return True, (str(ligne["compte_id"]) if ligne["compte_id"] else None)


_DERNIERE_VERSION = (
    "SELECT DISTINCT ON (v.releve_id) v.* FROM releve_version v"
    " ORDER BY v.releve_id, v.version DESC"
)


def _vue(ligne: dict, lecteur_id: str | None, emails: dict) -> dict:
    compte = str(ligne["compte_id"]) if ligne["compte_id"] else None
    return {
        "id": str(ligne["id"]),
        "point_id": ligne["point_id"],
        "point_nom": ligne["point_nom"],
        "point_designation": ligne["point_designation"],
        "niveau_estime": ligne["niveau_estime"],
        "cree_le": ligne["cree_le"].isoformat(),
        "version": ligne["version"],
        "niveau": ligne["niveau"],
        "profondeur_mm": ligne["profondeur_mm"],
        "instrument": ligne["instrument"],
        "observation": ligne["observation"],
        "annee_refection": ligne["annee_refection"],
        "source_refection": ligne["source_refection"],
        "auteur": pseudonyme(compte, emails.get(compte), lecteur_id),
        "est_auteur": compte is not None and compte == str(lecteur_id),
        "nb_photos": ligne["nb_photos"],
        "position_eloignee": (ligne["distance_point_m"] or 0) > DISTANCE_ELOIGNEE_M,
    }


def _releves(conn, filtre: str, parametres: tuple) -> list[dict]:
    """``filtre`` est toujours une constante de ce module ; les valeurs passent en
    paramètres, jamais dans la chaîne."""
    return conn.execute(
        "SELECT r.*, v.version, v.niveau, v.profondeur_mm, v.instrument, v.observation,"  # noqa: S608
        " v.annee_refection, v.source_refection, c.email,"
        " (SELECT count(*) FROM photo p WHERE p.releve_id = r.id AND p.etat = 'visible')"
        " AS nb_photos"
        f" FROM releve r JOIN ({_DERNIERE_VERSION}) v ON v.releve_id = r.id"
        " LEFT JOIN compte c ON c.id = r.compte_id"
        f" WHERE r.retire_le IS NULL AND {filtre}"
        " ORDER BY r.cree_le DESC",
        parametres,
    ).fetchall()


def releves_visibles(commune_insee: str, lecteur_id: str | None) -> list[dict]:
    """Tous les relevés visibles de la commune (dernière version), du plus récent au plus
    ancien, avec la position du téléphone et, pour les relevés du lecteur seulement, les
    identifiants de photos (FR-013, FR-015)."""
    with connexion() as conn:
        lignes = _releves(conn, "r.commune_insee = %s", (commune_insee,))
        siens = [li["id"] for li in lignes if str(li["compte_id"]) == str(lecteur_id)]
        photos = (
            conn.execute(
                "SELECT id, releve_id FROM photo WHERE etat = 'visible' AND releve_id = ANY(%s)"
                " ORDER BY cree_le",
                (siens,),
            ).fetchall()
            if siens
            else []
        )
    emails = {str(li["compte_id"]): li["email"] for li in lignes if li["compte_id"]}
    vues = []
    for ligne in lignes:
        vue = _vue(ligne, lecteur_id, emails) | {"lon": ligne["lon"], "lat": ligne["lat"]}
        vue["photos"] = [str(p["id"]) for p in photos if str(p["releve_id"]) == vue["id"]]
        vues.append(vue)
    return vues


def derniers_releves(commune_insee: str, lecteur_id: str | None) -> dict[str, dict]:
    """Dernier relevé visible de chaque point relevé de la commune, avec le nombre de relevés
    (US2, FR-006) ; aucune information de photo autre que leur nombre (FR-015)."""
    with connexion() as conn:
        lignes = _releves(conn, "r.commune_insee = %s", (commune_insee,))
    emails = {str(li["compte_id"]): li["email"] for li in lignes if li["compte_id"]}
    resultat: dict[str, dict] = {}
    for ligne in lignes:  # du plus récent au plus ancien
        point = ligne["point_id"]
        if point not in resultat:
            resultat[point] = _vue(ligne, lecteur_id, emails) | {"nb_releves": 0}
        resultat[point]["nb_releves"] += 1
    return resultat


def historique(commune_insee: str, point_id: str, lecteur_id: str | None) -> list[dict]:
    """Relevés d'un point ; identifiants de photos **seulement** pour les relevés du lecteur
    (FR-015)."""
    with connexion() as conn:
        lignes = _releves(
            conn, "r.commune_insee = %s AND r.point_id = %s", (commune_insee, point_id)
        )
        siens = [li["id"] for li in lignes if str(li["compte_id"]) == str(lecteur_id)]
        photos_siennes = (
            conn.execute(
                "SELECT id, releve_id FROM photo WHERE etat = 'visible' AND releve_id = ANY(%s)"
                " ORDER BY cree_le",
                (siens,),
            ).fetchall()
            if siens
            else []
        )
    emails = {str(li["compte_id"]): li["email"] for li in lignes if li["compte_id"]}
    vues = [_vue(li, lecteur_id, emails) for li in lignes]
    for vue in vues:
        if vue["est_auteur"]:
            vue["photos"] = [
                str(p["id"]) for p in photos_siennes if str(p["releve_id"]) == vue["id"]
            ]
    return vues


def releve(releve_id: str, lecteur_id: str | None) -> dict | None:
    """Un relevé avec toutes ses versions (du plus récent au plus ancien)."""
    with connexion() as conn:
        lignes = _releves(conn, "r.id = %s", (releve_id,))
        if not lignes:
            return None
        versions = conn.execute(
            "SELECT * FROM releve_version WHERE releve_id = %s ORDER BY version DESC",
            (releve_id,),
        ).fetchall()
    emails = {str(li["compte_id"]): li["email"] for li in lignes if li["compte_id"]}
    vue = _vue(lignes[0], lecteur_id, emails)
    vue["versions"] = [
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(ve).items()}
        | {"releve_id": releve_id}
        for ve in versions
    ]
    return vue
