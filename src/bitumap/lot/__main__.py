"""Point d'entrée du job de lot : ``python -m bitumap.lot`` (contracts/lot-job.md).

Déclenché toutes les 15 minutes ; file vide ⇒ fin immédiate (SC-008). Codes de sortie :
0 lot traité (même avec des communes en échec), 1 erreur d'infrastructure.
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from bitumap import courriel
from bitumap.db.purge import purger
from bitumap.ia.budget import alerter_une_fois
from bitumap.journal import configurer_journalisation, evenement
from bitumap.lot import commune, regional
from bitumap.lot import prise_en_charge as file
from bitumap.sources import ortho
from bitumap.sources.fournisseur import FournisseurEnLigne

journal = logging.getLogger("bitumap.lot")
DOSSIER_CACHE = Path(tempfile.gettempdir()) / "bitumap-cache"  # disque éphémère du job


def executer(
    dossier_cache: Path = DOSSIER_CACHE,
    fabrique=None,
    vignettes=None,
    appel_ia=None,
    regional_fn=regional.preparer,
) -> list[commune.Resultat]:
    purger()
    file.reprendre_les_lots_interrompus()
    lot_id = file.ouvrir_lot()
    demandes = file.prendre(lot_id)
    if not demandes:
        file.clore_lot(lot_id, None, 0)
        journal.info("file vide : fin du lot")
        return []
    t0 = time.perf_counter()
    donnees = regional_fn(dossier_cache)
    if fabrique is None:
        fabrique = partial(
            FournisseurEnLigne, osm_regional=donnees.osm_gpkg, osm_date=donnees.osm_date
        )
    vignettes = vignettes or ortho.vignettes_historiques
    resultats = [commune.traiter(d, lot_id, fabrique, vignettes, appel_ia) for d in demandes]
    statuts = Counter(r.statut for r in resultats)
    cout_ia = sum(r.cout_ia for r in resultats)
    file.clore_lot(lot_id, donnees.duree_s, cout_ia, statuts)
    evenement(
        journal,
        "lot.termine",
        lot_id=lot_id,
        nb_demandes=len(demandes),
        statuts=dict(statuts),
        duree_s=round(time.perf_counter() - t0, 1),
        duree_regionale_s=donnees.duree_s,
        cout_ia_eur=round(cout_ia, 4),
    )
    echecs = [r for r in resultats if r.statut == "en_echec"]
    if echecs:
        courriel.envoyer(
            courriel.alerte_mainteneur(
                f"lot : {len(echecs)} commune(s) en échec",
                "Communes en échec : "
                + ", ".join(r.commune for r in echecs)
                + f". Durée du lot : {time.perf_counter() - t0:.0f} s. Voir le journal (Cockpit).",
            )
        )
    return resultats


def alerter_erreur_infrastructure(erreur: Exception) -> None:
    """Lot interrompu (base, stockage…) : une alerte par heure au plus ; si la base est
    elle-même injoignable, l'alerte part sans déduplication."""
    sujet = f"lot interrompu : {type(erreur).__name__}"
    texte = "Le lot s'est arrêté sur une erreur d'infrastructure. Détail dans le journal (Cockpit)."
    try:
        alerter_une_fois(f"lot_infrastructure:{datetime.now(UTC):%Y-%m-%dT%H}", sujet, texte)
    except Exception:
        courriel.envoyer(courriel.alerte_mainteneur(sujet, texte))


def main(argv=None) -> int:
    configurer_journalisation()
    parser = argparse.ArgumentParser(description="Traite un lot de demandes de rapport.")
    parser.add_argument("--cache", type=Path, default=DOSSIER_CACHE)
    args = parser.parse_args(argv)
    try:
        resultats = executer(args.cache)
    except Exception as erreur:
        journal.exception("erreur d'infrastructure")
        try:
            alerter_erreur_infrastructure(erreur)
        except Exception:
            journal.exception("alerte au mainteneur impossible")
        return 1
    for r in resultats:
        journal.info("%s : %s", r.commune, r.statut)
    return 0


if __name__ == "__main__":
    sys.exit(main())
