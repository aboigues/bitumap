"""File d'attente (contracts/lot-job.md) : prise en charge exclusive, reprise, report."""

from __future__ import annotations

from bitumap.config import reglages
from bitumap.db import connexion


def ouvrir_lot() -> str:
    with connexion() as conn:
        return str(conn.execute("INSERT INTO lot DEFAULT VALUES RETURNING id").fetchone()["id"])


def reprendre_les_lots_interrompus() -> int:
    """Demandes « en cours » depuis plus de la durée maximale d'un lot : remises en tête de file
    (nouvelle tentative) ou en échec après deux tentatives (FR-017)."""
    heures = reglages().lot_delai_max_h
    with connexion() as conn:
        reprises = conn.execute(
            "UPDATE demande SET etat = 'en_file', etape = NULL, lot_id = NULL,"
            " tentatives = tentatives + 1"
            " WHERE etat = 'en_cours' AND tentatives < 2"
            " AND pris_en_charge_le < now() - make_interval(hours => %s)"
            " RETURNING id",
            (heures,),
        ).fetchall()
        conn.execute(
            "UPDATE demande SET etat = 'en_echec', termine_le = now(),"
            " erreur_publique = 'La génération a été interrompue.'"
            " WHERE etat = 'en_cours' AND tentatives >= 2"
            " AND pris_en_charge_le < now() - make_interval(hours => %s)",
            (heures,),
        )
    return len(reprises)


def prendre(lot_id: str, taille: int | None = None) -> list[dict]:
    """Prend jusqu'à ``taille`` demandes en file, de façon exclusive (SKIP LOCKED) : deux lots
    concurrents ne prennent jamais la même demande (FR-007d)."""
    taille = taille or reglages().lot_taille
    with connexion() as conn:
        demandes = conn.execute(
            "UPDATE demande SET etat = 'en_cours', lot_id = %s, pris_en_charge_le = now(),"
            " reportee = false"
            " WHERE id IN (SELECT id FROM demande WHERE etat = 'en_file'"
            "   ORDER BY cree_le LIMIT %s FOR UPDATE SKIP LOCKED)"
            " RETURNING id, commune_insee, commune_nom, empreinte",
            (lot_id, taille),
        ).fetchall()
        conn.execute("UPDATE lot SET nb_demandes = %s WHERE id = %s", (len(demandes), lot_id))
    return [dict(d) for d in demandes]


def etape(demande_id: str, nom: str) -> None:
    with connexion() as conn:
        conn.execute("UPDATE demande SET etape = %s WHERE id = %s", (nom, demande_id))


def terminer(demande_id: str, empreinte: str) -> None:
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'terminee', etape = NULL, termine_le = now(),"
            " empreinte = %s WHERE id = %s",
            (empreinte, demande_id),
        )


def echouer(demande_id: str, message_public: str) -> None:
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'en_echec', etape = NULL, termine_le = now(),"
            " erreur_publique = %s WHERE id = %s",
            (message_public, demande_id),
        )


def reporter(demande_id: str) -> None:
    """Budget IA du jour insuffisant : la demande retourne en file pour le lendemain."""
    with connexion() as conn:
        conn.execute(
            "UPDATE demande SET etat = 'en_file', etape = NULL, lot_id = NULL, reportee = true"
            " WHERE id = %s",
            (demande_id,),
        )


def demandeurs(demande_id: str) -> list[str]:
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT c.email FROM demandeur_demande d JOIN compte c ON c.id = d.compte_id"
            " WHERE d.demande_id = %s",
            (demande_id,),
        ).fetchall()
    return [ligne["email"] for ligne in lignes]


def clore_lot(
    lot_id: str,
    duree_regionale_s: float | None,
    cout_ia,
    statuts: dict[str, int] | None = None,
) -> None:
    """Clôture : durée régionale, coût IA et résultat par commune (T069)."""
    statuts = statuts or {}
    with connexion() as conn:
        conn.execute(
            "UPDATE lot SET termine_le = now(), duree_regionale_s = %s, cout_ia_eur = %s,"
            " nb_terminees = %s, nb_echecs = %s, nb_reportees = %s WHERE id = %s",
            (
                duree_regionale_s,
                cout_ia,
                statuts.get("terminee", 0),
                statuts.get("en_echec", 0),
                statuts.get("reportee", 0),
                lot_id,
            ),
        )
