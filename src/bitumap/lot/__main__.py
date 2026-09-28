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
from functools import partial
from pathlib import Path

from bitumap import courriel
from bitumap.db.purge import purger
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
    file.clore_lot(lot_id, donnees.duree_s, sum(r.cout_ia for r in resultats))
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


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Traite un lot de demandes de rapport.")
    parser.add_argument("--cache", type=Path, default=DOSSIER_CACHE)
    args = parser.parse_args(argv)
    try:
        resultats = executer(args.cache)
    except Exception:
        journal.exception("erreur d'infrastructure")
        return 1
    for r in resultats:
        journal.info("%s : %s", r.commune, r.statut)
    return 0


if __name__ == "__main__":
    sys.exit(main())
