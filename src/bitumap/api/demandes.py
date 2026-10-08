"""Communes, demandes de rapport, suivi et consultation (contracts/http-api.md ; US1, US2).

Ordre des contrôles de ``POST /demandes`` : antibot → cache → rattachement → budget IA du
jour → quota du compte → quota global → création. Consulter un rapport en cache ou se
rattacher à une demande active ne consomme aucun quota (FR-005, US2-6) ; les quotas ne
sont décomptés qu'à la création, dans la même transaction que l'insertion.
"""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from bitumap import stockage, territoire
from bitumap.api import antibot, quotas
from bitumap.api.application import ErreurPublique, gabarits
from bitumap.api.auth import SessionRequise, verifier_csrf
from bitumap.api.navigation import fil
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.ia.budget import budget_jour_epuise
from bitumap.lot import temoin, versions
from bitumap.rapport.rendu import csp_du_document, json_dans_html
from bitumap.score.methode import VERSION_METHODE
from bitumap.terrain import classement
from bitumap.terrain import depot as releves_terrain
from bitumap.territoire import ErreurTerritoire, commune_par_insee, communes_du_code_postal
from bitumap.territoire.recherche import SEUIL, normaliser

routeur = APIRouter()
_EMPREINTE = re.compile(r"^[0-9a-f]{16}$")
_INSEE = re.compile(r"^\d{5}$")
DUREE_LOT_DEFAUT_MIN = 15


def _erreur_territoire(e: ErreurTerritoire) -> ErreurPublique:
    statut = 404 if e.code == "code_inexistant" else 400
    return ErreurPublique(statut, e.code, e.message)


def rapport_valide(insee: str) -> str | None:
    """Empreinte d'un rapport réutilisable (FR-008) : même empreinte courante et moins de
    ``cache_rapport_jours`` jours ; sinon ``None``."""
    empreinte = versions.empreinte_courante(insee)
    produit_le = stockage.date_rapport(insee, empreinte)
    if produit_le is None:
        return None
    limite = datetime.now(UTC) - timedelta(days=reglages().cache_rapport_jours)
    return empreinte if produit_le >= limite else None


QUOTA_COMPTE = (429, "quota_compte", "Limite de demandes du jour atteinte : réessayez demain.")
QUOTA_GLOBAL = (
    429,
    "quota_global",
    "Le service a atteint sa limite de rapports du jour : réessayez demain.",
)
BUDGET_EPUISE = (
    429,
    "budget_ia_epuise",
    "Le budget d'analyse du jour est épuisé : réessayez demain.",
)


def _decompter(conn, compte_id: str) -> None:
    """Décompte atomique des deux quotas ; un dépassement annule toute la transaction."""
    r = reglages()
    if not quotas.consommer(
        conn, quotas.generation_compte(compte_id), quotas.JOUR, r.quota_generation_compte_jour
    ):
        raise ErreurPublique(*QUOTA_COMPTE)
    if not quotas.consommer(
        conn, quotas.GENERATION_GLOBALE, quotas.JOUR, r.quota_generation_global_jour
    ):
        raise ErreurPublique(*QUOTA_GLOBAL)


def _demande_active(conn, empreinte: str):
    return conn.execute(
        "SELECT id FROM demande WHERE empreinte = %s AND etat IN ('en_file', 'en_cours')",
        (empreinte,),
    ).fetchone()


def _creer_ou_rattacher(commune, empreinte: str, compte_id: str) -> str:
    with connexion() as conn:
        existante = _demande_active(conn, empreinte)
        if existante is None:
            if budget_jour_epuise():
                raise ErreurPublique(*BUDGET_EPUISE)
            cree = conn.execute(
                "INSERT INTO demande (commune_insee, commune_nom, empreinte)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (empreinte) WHERE etat IN ('en_file', 'en_cours') DO NOTHING"
                " RETURNING id",
                (commune.insee, commune.nom, empreinte),
            ).fetchone()
            if cree is None:  # créée entre-temps par un autre compte
                existante = _demande_active(conn, empreinte)
        if existante is not None:  # rattachement sans décompte (US2-6)
            demande_id, compte_quota = existante["id"], False
        else:
            demande_id, compte_quota = cree["id"], True
            _decompter(conn, compte_id)
        conn.execute(
            "INSERT INTO demandeur_demande (demande_id, compte_id, compte_quota)"
            " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (demande_id, compte_id, compte_quota),
        )
        # Dans la transaction : sans témoin, pas de mise en file (le job ne verrait pas la
        # demande avant son passage quotidien, T096).
        temoin.signaler(str(demande_id))
    return demande_id


_CODE_POSTAL = re.compile(r"^\d{5}$")
GEO_INDISPONIBLE = "Recherche par code postal indisponible : cherchez par le nom de la commune."
AUCUNE_COMMUNE = "Aucune commune trouvée : le service couvre l'Île-de-France seulement."
TROP_COURT = "Saisissez au moins 3 lettres du nom de la commune, ou son code postal."


@routeur.get("/communes/recherche")
def propositions(session: SessionRequise, q: str = "") -> JSONResponse:
    """Propositions pendant la frappe (008 R2) : liste intégrée, aucun appel externe."""
    trouvees = territoire.rechercher(q)
    return JSONResponse(
        [{"insee": c.insee, "nom": c.nom, "departement": c.departement} for c in trouvees],
        headers={"Cache-Control": "private, max-age=3600"},
    )


def chercher_communes(q: str) -> tuple[list, str | None]:
    """Communes pour une saisie (nom ou code postal) et message éventuel (FR-003, FR-007)."""
    q = q.strip()
    if _CODE_POSTAL.match(q):
        try:
            return communes_du_code_postal(q), None
        except ErreurTerritoire as e:
            return [], e.message
        except httpx.HTTPError:
            return [], GEO_INDISPONIBLE
    trouvees = territoire.rechercher(q)
    if trouvees:
        return trouvees, None
    trop_court = len(normaliser(q)) < SEUIL
    return [], TROP_COURT if trop_court else AUCUNE_COMMUNE


def communes_avec_rapport() -> list[territoire.Commune]:
    """Communes dont un rapport est disponible, quel que soit le compte qui l'a demandé
    (008 FR-010, R7) : dernière demande terminée depuis moins de ``cache_rapport_jours`` et
    d'empreinte courante (même règle que ``rapport_valide``, sans appel au stockage)."""
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT DISTINCT ON (commune_insee) commune_insee, commune_nom, empreinte"
            " FROM demande WHERE etat = 'terminee'"
            " AND termine_le >= now() - make_interval(days => %s)"
            " ORDER BY commune_insee, termine_le DESC",
            (reglages().cache_rapport_jours,),
        ).fetchall()
    disponibles = [
        territoire.par_insee(ligne["commune_insee"])
        or territoire.Commune(
            ligne["commune_insee"], ligne["commune_nom"], ligne["commune_insee"][:2]
        )
        for ligne in lignes
        if ligne["empreinte"] == versions.empreinte_courante(ligne["commune_insee"])
    ]
    return sorted(disponibles, key=lambda c: normaliser(c.nom))


def page_choix_commune(
    requete: Request, session, rubrique: str, q: str = "", insee: str = ""
) -> Response:
    """Choix d'une commune pour les relevés ou le parcours (008 US2, contracts/interface.md) ;
    ``insee`` : commune choisie parmi les propositions pendant la frappe."""
    disponibles = communes_avec_rapport()
    codes = {c.insee for c in disponibles}
    if insee in codes:
        return RedirectResponse(f"/{rubrique}/{insee}", status_code=303)
    choisie = territoire.par_insee(insee) if insee else None
    if choisie:
        trouvees, message = [choisie], None
    else:
        trouvees, message = chercher_communes(q) if q else ([], None)
    return gabarits.TemplateResponse(
        requete,
        "choix_commune.html",
        {
            "session": session,
            "rubrique": rubrique,
            "q": q,
            "message": message,
            "trouvees": [(c, c.insee in codes) for c in trouvees],
            "disponibles": disponibles,
        },
    )


@routeur.get("/communes")
def communes(
    requete: Request, session: SessionRequise, q: str = "", insee: str = "", code_postal: str = ""
) -> Response:
    message = None
    if insee:
        commune = territoire.par_insee(insee)
        if commune is None:
            raise ErreurPublique(404, "code_inexistant", "Commune inconnue.")
        liste = [commune]
    elif code_postal:  # anciens liens et formulaires (002)
        try:
            liste = communes_du_code_postal(code_postal)
        except ErreurTerritoire as e:
            raise _erreur_territoire(e) from e
        q = code_postal
    else:
        liste, message = chercher_communes(q)
    return gabarits.TemplateResponse(
        requete,
        "communes.html",
        {"session": session, "communes": liste, "q": q, "message": message},
    )


@routeur.post("/demandes")
def demander(
    requete: Request,
    session: SessionRequise,
    insee: Annotated[str, Form()] = "",
    csrf: Annotated[str, Form()] = "",
    altcha: Annotated[str, Form()] = "",
) -> Response:
    verifier_csrf(session, csrf)
    if not _INSEE.match(insee):
        raise ErreurPublique(400, "commune_invalide", "Commune inconnue.")
    try:
        commune = commune_par_insee(insee)
    except ErreurTerritoire as e:
        raise _erreur_territoire(e) from e
    antibot.verifier(altcha)

    empreinte = rapport_valide(commune.insee)
    if empreinte:
        return RedirectResponse(f"/rapports/{commune.insee}/{empreinte}", status_code=303)

    empreinte = versions.empreinte_courante(commune.insee)
    demande_id = _creer_ou_rattacher(commune, empreinte, session.compte_id)
    return RedirectResponse(f"/demandes/{demande_id}", status_code=303)


def _prochain_declenchement(maintenant: datetime) -> datetime:
    pas = reglages().lot_intervalle_min
    minutes = (maintenant.minute // pas + 1) * pas
    base = maintenant.replace(minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minutes)


def _duree_moyenne_lot_min() -> float:
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT avg(extract(epoch FROM termine_le - demarre_le)) / 60 AS m FROM"
            " (SELECT * FROM lot WHERE termine_le IS NOT NULL AND nb_demandes > 0"
            "  ORDER BY demarre_le DESC LIMIT 10) l"
        ).fetchone()
    return float(ligne["m"]) if ligne and ligne["m"] else DUREE_LOT_DEFAUT_MIN


def suivi_de(demande_id: str, compte_id: str) -> dict | None:
    with connexion() as conn:
        d = conn.execute(
            "SELECT d.* FROM demande d JOIN demandeur_demande dd ON dd.demande_id = d.id"
            " WHERE d.id = %s AND dd.compte_id = %s",
            (demande_id, compte_id),
        ).fetchone()
        if d is None:
            return None
        position = None
        if d["etat"] == "en_file":
            position = conn.execute(
                "SELECT count(*) + 1 AS p FROM demande WHERE etat = 'en_file' AND cree_le < %s",
                (d["cree_le"],),
            ).fetchone()["p"]
    suivi = dict(d)
    suivi["position"] = position
    if position is not None:
        lots_avant = math.ceil(position / reglages().lot_taille) - 1
        debut = _prochain_declenchement(datetime.now(UTC))
        suivi["heure_estimee"] = debut + timedelta(
            minutes=lots_avant * reglages().lot_intervalle_min + _duree_moyenne_lot_min()
        )
    return suivi


@routeur.get("/demandes/{demande_id}")
def suivi(requete: Request, demande_id: str, session: SessionRequise) -> Response:
    try:
        donnees = suivi_de(demande_id, session.compte_id)
    except Exception as e:  # identifiant mal formé
        raise ErreurPublique(404, "demande_inconnue", "Demande introuvable.") from e
    if donnees is None:
        raise ErreurPublique(404, "demande_inconnue", "Demande introuvable.")
    return gabarits.TemplateResponse(
        requete, "suivi.html", {"session": session, "demande": donnees}
    )


@routeur.get("/demandes")
def mes_demandes(requete: Request, session: SessionRequise) -> Response:
    with connexion() as conn:
        lignes = conn.execute(
            "SELECT d.id, d.commune_nom, d.commune_insee, d.empreinte, d.etat, d.cree_le"
            " FROM demande d JOIN demandeur_demande dd ON dd.demande_id = d.id"
            " WHERE dd.compte_id = %s ORDER BY d.cree_le DESC LIMIT 100",
            (session.compte_id,),
        ).fetchall()
    return gabarits.TemplateResponse(
        requete, "demandes.html", {"session": session, "demandes": lignes}
    )


def _fichier_rapport(insee: str, empreinte: str, nom: str) -> bytes:
    if not _INSEE.match(insee) or not _EMPREINTE.match(empreinte):
        raise ErreurPublique(404, "rapport_inconnu", "Rapport introuvable.")
    contenu = stockage.lire(
        reglages().bucket_rapports, stockage.prefixe_rapport(insee, empreinte) + nom
    )
    if contenu is None:
        raise ErreurPublique(404, "rapport_inconnu", "Rapport introuvable.")
    return contenu


_BODY = re.compile(r"<body\b[^>]*>", re.IGNORECASE)


def _menu_du_rapport(insee: str, session) -> str:
    """Menu et fil du compte qui consulte (008 R6, FR-015) : ni script ni formulaire."""
    commune = territoire.par_insee(insee)
    return gabarits.get_template("rapport_menu.html").render(
        session=session,
        rubrique="demandes",
        fil=fil(("Mes demandes", "/demandes"), (commune.nom if commune else insee, None)),
    )


def _inserer_apres_body(html: str, bloc: str) -> str:
    """Insère ``bloc`` juste après la balise ``<body>`` (présente dans toutes les versions du
    gabarit du rapport) ; à défaut, en tête du document. Le rapport stocké n'est pas modifié."""
    balise = _BODY.search(html)
    if balise is None:
        return bloc + html
    return f"{html[: balise.end()]}\n{bloc}{html[balise.end() :]}"


def _inserer_avant_script(html: str, bloc: str) -> str:
    """Insère ``bloc`` juste après le bloc ``donnees``, donc avant le script du rapport qui le
    lit au chargement (inséré après, il serait ignoré). Le JSON échappe ``</`` : la première
    balise ``</script>`` qui suit est bien la fin du bloc."""
    ouverture = html.find('id="donnees"')
    fin = html.find("</script>", ouverture) if ouverture != -1 else -1
    if fin == -1:
        debut, balise, reste = html.rpartition("</body>")
        return f"{debut}{bloc}\n{balise}{reste}" if balise else html + bloc
    fin += len("</script>")
    return f"{html[:fin]}\n{bloc}{html[fin:]}"


def _classement_terrain(insee: str, empreinte: str) -> dict | None:
    """Classement corrigé d'un rapport 2.0 ; ``None`` pour un rapport 1.x, sans été de
    référence (produit avant 004 T028) ou incomplet (``journal.json`` ou ``points.geojson``
    absent) : le rapport est alors servi sans ce bloc, jamais refusé."""
    prefixe = stockage.prefixe_rapport(insee, empreinte)
    journal_rapport = stockage.lire(reglages().bucket_rapports, prefixe + "journal.json")
    if (
        journal_rapport is None
        or json.loads(journal_rapport).get("version_methode", VERSION_METHODE) == VERSION_METHODE
    ):
        return None
    contenu = stockage.lire(reglages().bucket_rapports, prefixe + "points.geojson")
    if contenu is None:
        return None
    points = json.loads(contenu)
    ete = (points.get("ete_reference") or {}).get("annee")
    if ete is None:
        return None
    return classement.corriger(points, classement.refections(insee), int(ete))


@routeur.get("/rapports/{insee}/{empreinte}")
def rapport(insee: str, empreinte: str, session: SessionRequise) -> Response:
    html = _fichier_rapport(insee, empreinte, "rapport.html").decode("utf-8")
    # Constaté (003 US2) : relevés courants insérés à chaque consultation, sans modifier le
    # rapport stocké ni le score ; données non exécutées, aucune photo (FR-015).
    constate = releves_terrain.derniers_releves(insee, session.compte_id)
    bloc = f'<script type="application/json" id="releves">{json_dans_html(constate)}</script>'
    # Méthode 2.0 : classement corrigé par le terrain (004 R9), juste après « releves » ;
    # couche distincte, rien n'est écrit dans le stockage (principe VI).
    corrige = _classement_terrain(insee, empreinte)
    if corrige is not None:
        bloc += (
            '\n<script type="application/json" id="classement-terrain">'
            f"{json_dans_html(corrige)}</script>"
        )
    html = _inserer_avant_script(html, bloc)
    html = _inserer_apres_body(html, _menu_du_rapport(insee, session))
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers={
            # Script autorisé : celui du document servi (003 R2, rapports en cache).
            "Content-Security-Policy": csp_du_document(html),
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )


@routeur.get("/rapports/{insee}/{empreinte}/points.geojson")
def points_geojson(insee: str, empreinte: str, session: SessionRequise) -> Response:
    return Response(
        _fichier_rapport(insee, empreinte, "points.geojson"),
        media_type="application/geo+json",
        headers={"Cache-Control": "private, no-store"},
    )
