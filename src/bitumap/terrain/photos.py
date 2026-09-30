"""Photos des relevés (003 R4, R5, R8 ; FR-003, FR-015, FR-018 à FR-020).

1. Le téléphone réduit la photo, puis l'envoie directement au stockage par un formulaire
   signé (POST présigné, validité courte, taille et type bornés par la politique) dans le
   préfixe ``quarantaine/``.
2. À la confirmation, le serveur relit l'objet, vérifie qu'il s'agit bien d'une image,
   la réencode en JPEG **sans aucune métadonnée**, l'écrit sous sa clé définitive et supprime
   la quarantaine. Tout échec supprime l'objet.
3. Une photo n'est servie qu'à son auteur et au mainteneur.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from PIL import Image, UnidentifiedImageError

from bitumap import stockage
from bitumap.api import quotas
from bitumap.api.application import ErreurPublique
from bitumap.config import reglages
from bitumap.db import connexion
from bitumap.ia.budget import alerter_une_fois

TYPES_ACCEPTES = ("image/jpeg", "image/png")
QUALITE_JPEG = 85


def cle_quarantaine(photo_id: str) -> str:
    return f"quarantaine/{photo_id}"


def cle_definitive(insee: str, point_id: str, releve_id: str, photo_id: str) -> str:
    return f"communes/{insee}/points/{point_id}/{releve_id}/{photo_id}.jpg"


def _releve_de_l_auteur(conn, releve_id: str, compte_id: str) -> dict:
    ligne = conn.execute(
        "SELECT id, commune_insee, point_id, compte_id FROM releve"
        " WHERE id = %s AND retire_le IS NULL",
        (releve_id,),
    ).fetchone()
    if ligne is None:
        raise ErreurPublique(404, "releve_inconnu", "Relevé introuvable.")
    if str(ligne["compte_id"]) != str(compte_id):
        raise ErreurPublique(403, "pas_auteur", "Seul l'auteur du relevé peut ajouter des photos.")
    return ligne


def _stockage_utilise_go(conn) -> float:
    ligne = conn.execute(
        "SELECT coalesce(sum(octets), 0) AS total FROM photo WHERE etat <> 'retiree_mainteneur'"
    ).fetchone()
    return int(ligne["total"]) / 1024**3


def formulaire(
    compte_id: str, releve_id: str, photo_id: str, octets: int, type_contenu: str
) -> dict:
    """Formulaire d'envoi signé vers la quarantaine (contrat : `…/formulaire`)."""
    r = reglages()
    if type_contenu not in TYPES_ACCEPTES:
        raise ErreurPublique(400, "image_invalide", "Seules les photos JPEG ou PNG sont acceptées.")
    if octets <= 0 or octets > r.photo_max_octets:
        raise ErreurPublique(413, "photo_trop_lourde", "Photo trop lourde (10 Mo au plus).")
    with connexion() as conn:
        _releve_de_l_auteur(conn, releve_id, compte_id)
        existante = conn.execute(
            "SELECT releve_id, etat FROM photo WHERE id = %s", (photo_id,)
        ).fetchone()
        if existante is not None and str(existante["releve_id"]) != str(releve_id):
            raise ErreurPublique(409, "identifiant_pris", "Identifiant de photo déjà utilisé.")
        if existante is not None and existante["etat"].startswith("retiree"):
            raise _photo_retiree()  # un nouvel envoi ne doit pas annuler un retrait (LL-014)
        if existante is None:
            nombre = conn.execute(
                "SELECT count(*) AS n FROM photo WHERE releve_id = %s"
                " AND etat IN ('quarantaine', 'visible')",
                (releve_id,),
            ).fetchone()["n"]
            if nombre >= r.photos_par_releve:
                raise ErreurPublique(
                    409, "trop_de_photos", f"{r.photos_par_releve} photos au plus par relevé."
                )
            if _stockage_utilise_go(conn) >= r.photos_max_go:
                alerter_une_fois(
                    f"stockage_photos:{datetime.now(UTC):%Y-%m-%d}",
                    "stockage des photos de relevés plein",
                    f"Le plafond de {r.photos_max_go} Go est atteint : les nouvelles photos"
                    " sont refusées (BITUMAP_PHOTOS_MAX_GO).",
                )
                raise ErreurPublique(
                    507, "stockage_plein", "Stockage des photos plein : réessayez plus tard."
                )
            if not quotas.consommer(
                conn, f"photo:compte:{compte_id}", quotas.JOUR, r.quota_photos_compte_jour
            ):
                raise ErreurPublique(
                    429, "quota_photos", "Limite de photos du jour atteinte : réessayez demain."
                )
            conn.execute(
                "INSERT INTO photo (id, releve_id, cle_objet) VALUES (%s, %s, %s)",
                (photo_id, releve_id, cle_quarantaine(photo_id)),
            )
    envoi = stockage._client().generate_presigned_post(
        Bucket=r.bucket_terrain,
        Key=cle_quarantaine(photo_id),
        Fields={"Content-Type": type_contenu},
        Conditions=[
            {"Content-Type": type_contenu},
            ["content-length-range", 1, r.photo_max_octets],
        ],
        ExpiresIn=r.photo_formulaire_validite_s,
    )
    return {"url": envoi["url"], "champs": envoi["fields"]}


def _supprimer_quarantaine(photo_id: str) -> None:
    # Toutes les versions : l'original (EXIF, GPS) ne doit pas survivre au réencodage.
    stockage.effacer_definitivement(reglages().bucket_terrain, cle_quarantaine(photo_id))


def reencoder(contenu: bytes) -> tuple[bytes, int, int]:
    """Vérifie le contenu réel (FR-019) et réencode en JPEG sans aucune métadonnée."""
    try:
        with Image.open(io.BytesIO(contenu)) as image:
            image.verify()
        with Image.open(io.BytesIO(contenu)) as image:
            if image.format not in ("JPEG", "PNG"):
                raise ValueError(image.format)
            propre = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as erreur:
        raise ErreurPublique(
            400, "image_invalide", "Le fichier n'est pas une image valide."
        ) from erreur
    tampon = io.BytesIO()
    propre.save(tampon, format="JPEG", quality=QUALITE_JPEG)  # aucune métadonnée transmise
    return tampon.getvalue(), propre.width, propre.height


def confirmer(
    compte_id: str,
    releve_id: str,
    photo_id: str,
    lon: float | None = None,
    lat: float | None = None,
    prise_le: datetime | None = None,
) -> dict:
    r = reglages()
    with connexion() as conn:
        ligne = _releve_de_l_auteur(conn, releve_id, compte_id)
        photo = conn.execute(
            "SELECT etat FROM photo WHERE id = %s AND releve_id = %s", (photo_id, releve_id)
        ).fetchone()
    if photo is None:
        raise ErreurPublique(404, "envoi_absent", "Aucun envoi pour cette photo.")
    if photo["etat"] == "visible":
        _supprimer_quarantaine(photo_id)  # dépôt rejoué après succès : original effacé
        return {"id": photo_id, "etat": "visible"}  # confirmation rejouée : idempotente
    if photo["etat"] != "quarantaine":
        _supprimer_quarantaine(photo_id)  # envoi refusé : l'original (EXIF) ne reste pas
        raise _photo_retiree()
    brut = stockage.lire(r.bucket_terrain, cle_quarantaine(photo_id))
    if brut is None:
        raise ErreurPublique(404, "envoi_absent", "La photo n'a pas été reçue : renvoyez-la.")
    try:
        propre, largeur, hauteur = reencoder(brut)
    except ErreurPublique:
        _supprimer_quarantaine(photo_id)
        with connexion() as conn:
            conn.execute("DELETE FROM photo WHERE id = %s", (photo_id,))
        raise
    cle = cle_definitive(ligne["commune_insee"], ligne["point_id"], releve_id, photo_id)
    stockage.ecrire(r.bucket_terrain, cle, propre, "image/jpeg")
    _supprimer_quarantaine(photo_id)
    with connexion() as conn:
        rendue_visible = conn.execute(
            "UPDATE photo SET etat = 'visible', cle_objet = %s, octets = %s, largeur = %s,"
            " hauteur = %s, lon = %s, lat = %s, prise_le = %s"
            " WHERE id = %s AND etat = 'quarantaine'",
            (cle, len(propre), largeur, hauteur, lon, lat, prise_le, photo_id),
        ).rowcount
    if not rendue_visible:  # retirée ou confirmée entre-temps : rien ne doit rester (LL-014)
        with connexion() as conn:
            etat = conn.execute("SELECT etat FROM photo WHERE id = %s", (photo_id,)).fetchone()
        if etat is None or etat["etat"] != "visible":
            stockage.effacer_definitivement(r.bucket_terrain, cle)
            raise _photo_retiree()
    return {"id": photo_id, "etat": "visible"}


def _photo_retiree() -> ErreurPublique:
    return ErreurPublique(
        409, "photo_retiree", "Cette photo a été retirée : elle ne peut être renvoyée."
    )


def retirer_par_auteur(photo_id: str, compte_id: str, motif: str | None) -> None:
    """Retrait par l'auteur (R12) : photo masquée partout, fichier **conservé** (historique,
    FR-012), trace (qui, quand, motif). Un autre compte reçoit ``404`` (aucune fuite
    d'existence, R5) ; un retrait rejoué est sans effet."""
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT p.etat, r.compte_id FROM photo p JOIN releve r ON r.id = p.releve_id"
            " WHERE p.id = %s",
            (photo_id,),
        ).fetchone()
        if ligne is None or str(ligne["compte_id"]) != str(compte_id):
            raise ErreurPublique(404, "http", "Page introuvable.")
        if ligne["etat"] != "visible":
            return
        conn.execute(
            "UPDATE photo SET etat = 'retiree_auteur', retire_le = now(), retire_par = %s,"
            " motif_retrait = %s WHERE id = %s",
            (compte_id, (motif or "").strip()[:200] or "erreur", photo_id),
        )


def retirer_rgpd(photo_id: str, mainteneur_id: str, motif: str | None) -> None:
    """Retrait RGPD par le mainteneur (FR-016, SC-008) : **toutes les versions** du fichier
    supprimées du bucket versionné ; la ligne reste comme trace, sans fichier. Aussi pour une
    photo déjà retirée par son auteur (fichier conservé jusque-là). Rejoué : sans effet."""
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT etat, cle_objet FROM photo WHERE id = %s", (photo_id,)
        ).fetchone()
    if ligne is None:
        raise ErreurPublique(404, "http", "Page introuvable.")
    if ligne["etat"] == "retiree_mainteneur":
        return
    bucket = reglages().bucket_terrain
    stockage.effacer_definitivement(bucket, ligne["cle_objet"])
    stockage.effacer_definitivement(bucket, cle_quarantaine(photo_id))
    with connexion() as conn:
        conn.execute(
            "UPDATE photo SET etat = 'retiree_mainteneur', retire_le = now(), retire_par = %s,"
            " motif_retrait = %s WHERE id = %s",
            (mainteneur_id, (motif or "").strip()[:200] or "RGPD", photo_id),
        )


def lire(photo_id: str, compte_id: str, mainteneur: bool) -> bytes | None:
    """Contenu d'une photo visible, pour son auteur ou le mainteneur ; ``None`` sinon (R5).
    Le mainteneur voit aussi une photo retirée par son auteur (fichier conservé, modération)."""
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT p.cle_objet, r.compte_id FROM photo p JOIN releve r ON r.id = p.releve_id"
            " WHERE p.id = %s AND (p.etat = 'visible' OR (%s AND p.etat = 'retiree_auteur'))",
            (photo_id, mainteneur),
        ).fetchone()
    if ligne is None:
        return None
    if not mainteneur and str(ligne["compte_id"]) != str(compte_id):
        return None
    return stockage.lire(reglages().bucket_terrain, ligne["cle_objet"])
