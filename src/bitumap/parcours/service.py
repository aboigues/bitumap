"""Calcul et conservation d'un parcours (006 T012, FR-001 à FR-007, FR-012).

Points du rapport en vigueur (rang estimé) filtrés par niveau ; départ à moins de
``DISTANCE_MAX_DEPART_M`` du centre des points ; sélection dans la durée (``selection``) ;
tracé final de la boucle par l'itinéraire de l'IGN. Le résumé reprend les durées **du tracé
final** ; si elles dépassaient la durée maximale (écart entre trajets isolés et tracé
enchaîné), le dernier point est rendu « non visité » et la boucle recalculée (SC-003).

Le parcours est gardé 24 h (table ``parcours``) ; l'adresse de départ n'est jamais écrite
dans les journaux.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

import httpx
from psycopg.types.json import Jsonb

from bitumap.db import connexion
from bitumap.parcours import geocodage, itineraire, selection
from bitumap.parcours.geocodage import Adresse
from bitumap.sources.base import SourceIndisponible, client_http
from bitumap.terrain.points import RapportEnVigueur, rapport_pour_parcours

DISTANCE_MAX_DEPART_M = 20_000
NIVEAUX = ("P1a", "P1b", "P1c", "P2", "P3")


class ErreurParcours(Exception):
    """Erreur présentée à l'agent : code stable, message sans détail technique."""

    def __init__(self, statut: int, code: str, message: str):
        super().__init__(code)
        self.statut, self.code, self.message = statut, code, message


def _minutes(secondes: float) -> int:
    return int(-(-secondes // 60))  # arrondi au-dessus


def rapport(insee: str) -> RapportEnVigueur:
    r = rapport_pour_parcours(insee)
    if r is None:
        raise ErreurParcours(404, "rapport_absent", "Aucun rapport en vigueur pour cette commune.")
    return r


def centre(r: RapportEnVigueur) -> tuple[float, float]:
    points = list(r.points.values())
    return (
        sum(p.lon for p in points) / len(points),
        sum(p.lat for p in points) / len(points),
    )


def _candidats(r: RapportEnVigueur, niveaux: list[str]) -> list[selection.Candidat]:
    return sorted(
        (
            selection.Candidat(p.id, p.rang, p.groupe, p.designation, p.lon, p.lat)
            for p in r.points.values()
            if p.groupe in niveaux
        ),
        key=lambda c: c.rang,
    )


def _boucle(depart, visites, mode, client) -> itineraire.Trajet:
    return itineraire.trajet([depart, *((v.lon, v.lat) for v in visites), depart], mode, client)


def _appliquer_trace(s: selection.Selection, trace: itineraire.Trajet, arret_s: float) -> None:
    """Cumuls, durée et distance totales recalculés sur les étapes du tracé final."""
    duree, distance = 0.0, 0.0
    for visite, (metres, secondes) in zip(s.visites, trace.etapes, strict=False):
        duree += secondes + arret_s
        distance += metres
        visite.duree_cumulee_s, visite.distance_cumulee_m = duree, distance
    s.duree_totale_s = trace.duree_s + arret_s * len(s.visites)
    s.distance_totale_m = trace.distance_m


def calculer(
    insee: str,
    compte_id: str,
    depart: Adresse,
    niveaux: list[str],
    mode: str,
    duree_max_min: int,
    arret_min: int,
    exclus: dict[str, str] | None = None,
    exclusion_releves_jours: int | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Calcule et enregistre le parcours ; renvoie son identifiant. ``exclus`` : points à
    écarter avec leur raison (US4)."""
    r = rapport(insee)
    candidats = _candidats(r, niveaux)
    exclus = exclus or {}
    ecartes = [c for c in candidats if c.point_id in exclus]
    candidats = [c for c in candidats if c.point_id not in exclus]
    if not candidats and not ecartes:
        raise ErreurParcours(400, "aucun_point", "Aucun point dans les niveaux choisis.")
    position = (depart.lon, depart.lat)
    if selection.vol_oiseau_m(position, centre(r)) > DISTANCE_MAX_DEPART_M:
        raise ErreurParcours(
            400, "depart_trop_loin", "Le départ doit être à moins de 20 km de la commune."
        )
    duree_max_s, arret_s = duree_max_min * 60, arret_min * 60
    fermer = client is None
    client = client or client_http(timeout=60)
    try:

        def duree(a, b):
            t = itineraire.trajet([a, b], mode, client)
            return t.duree_s, t.distance_m

        try:
            s = selection.selectionner(position, candidats, mode, duree_max_s, arret_s, duree)
        except selection.AucunPoint as erreur:
            raise ErreurParcours(
                400, "aucun_point", "Tous les points des niveaux choisis sont exclus."
            ) from erreur
        except selection.DureeInsuffisante as erreur:
            raise ErreurParcours(
                400,
                "duree_insuffisante",
                "Durée trop courte pour visiter un seul point : il faut au moins "
                f"{_minutes(erreur.duree_min_s)} minutes.",
            ) from erreur
        while True:
            trace = _boucle(position, s.visites, mode, client)
            _appliquer_trace(s, trace, arret_s)
            if s.duree_totale_s <= duree_max_s or len(s.visites) == 1:
                break
            dernier = s.visites.pop()
            s.non_visites.append(
                selection.NonVisite(dernier.point_id, dernier.rang, dernier.niveau, "duree")
            )
        s.duree_restante_s = duree_max_s - s.duree_totale_s
    except (SourceIndisponible, itineraire.Inaccessible) as erreur:
        raise ErreurParcours(
            503,
            "itineraire_indisponible",
            "Le service de calcul d'itinéraire est indisponible : réessayez dans quelques minutes.",
        ) from erreur
    finally:
        if fermer:
            client.close()
    s.non_visites += [
        selection.NonVisite(c.point_id, c.rang, c.niveau, exclus[c.point_id]) for c in ecartes
    ]
    s.non_visites.sort(key=lambda n: n.rang)
    resultat = {
        "visites": [asdict(v) for v in s.visites],
        "non_visites": [asdict(n) for n in s.non_visites],
        "trace": trace.geometrie,
        "troncons": trace.troncons,
        "resume": {
            "distance_m": round(s.distance_totale_m),
            "duree_s": round(s.duree_totale_s),
            "duree_arrets_s": arret_s * len(s.visites),
            "duree_retour_s": round(trace.etapes[-1][1]) if trace.etapes else 0,
            "duree_restante_s": round(s.duree_restante_s),
            "nb_visites": len(s.visites),
            "nb_non_visites": len(s.non_visites),
            "nb_exclus": len(ecartes),
            "rapport_empreinte": r.empreinte,
            "rapport_date": r.produit_le.date().isoformat(),
            "sources": [
                geocodage.provenance().en_dict(),
                itineraire.provenance().en_dict(),
            ],
        },
    }
    identifiant = str(uuid.uuid4())
    with connexion() as conn:
        conn.execute(
            "INSERT INTO parcours (id, compte_id, commune_insee, empreinte, depart_libelle,"
            " depart_lon, depart_lat, niveaux, mode, duree_max_min, arret_min,"
            " exclusion_releves_jours, resultat)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                identifiant,
                compte_id,
                insee,
                r.empreinte,
                depart.libelle,
                depart.lon,
                depart.lat,
                niveaux,
                mode,
                duree_max_min,
                arret_min,
                exclusion_releves_jours,
                Jsonb(resultat),
            ),
        )
    return identifiant


def lire(identifiant: str, compte_id: str) -> dict | None:
    """Parcours non expiré du compte ; ``None`` sinon (inconnu, expiré ou d'un autre compte)."""
    try:
        uuid.UUID(identifiant)
    except ValueError:
        return None
    with connexion() as conn:
        return conn.execute(
            "SELECT * FROM parcours WHERE id = %s AND compte_id = %s AND expire_le > now()",
            (identifiant, compte_id),
        ).fetchone()


def nom_commune(insee: str, empreinte: str) -> str:
    """Nom de la commune, lu dans le titre du rapport stocké (« Risque d'orniérage — X »)."""
    import html
    import re

    from bitumap import stockage
    from bitumap.config import reglages

    contenu = stockage.lire(
        reglages().bucket_rapports, stockage.prefixe_rapport(insee, empreinte) + "rapport.html"
    )
    trouve = re.search(rb"<title>[^<]*\xe2\x80\x94 ([^<]+)</title>", contenu or b"")
    return html.unescape(trouve.group(1).decode("utf-8")).strip() if trouve else insee
