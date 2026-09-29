"""Vérifie le widget ALTCHA auto-hébergé (T058) : aucun CDN, fichiers figés et vérifiés.

Usage :
  uv run python tools/verifier_altcha.py            # empreintes SHA-256 des fichiers servis
  uv run python tools/verifier_altcha.py --source   # + comparaison au paquet npm officiel,
                                                    #   dont l'intégrité sha512 est figée ici

Mise à jour du widget : changer ``VERSION`` et ``INTEGRITE_NPM`` (champ ``dist.integrity``
de https://registry.npmjs.org/altcha/<version>), recopier les fichiers depuis le paquet,
puis mettre à jour ``EMPREINTES`` avec la sortie de ``sha256sum``.
"""

from __future__ import annotations

import base64
import hashlib
import io
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "3.2.3"
INTEGRITE_NPM = (
    "sha512-yBHJIOoGZyU4/ap3AnlL2kChEVw40QP142BtxYZN5dCjAeBla"
    "ScuAEWxmrLDVQjlRBplayapUIvARs0eG48OVw=="
)
DOSSIER = Path(__file__).resolve().parents[1] / "src" / "bitumap" / "api" / "statique" / "altcha"

# fichier servi → (chemin dans le paquet npm, SHA-256)
EMPREINTES = {
    "altcha.min.js": (
        "package/dist/main/altcha.min.js",
        "102bb89eb6ee4556068e2514880b7755495b23d90438c751809cb4f0ecbd4efb",
    ),
    "fr-fr.js": (
        "package/dist/i18n/fr-fr.js",
        "62ce6e8d06a6c0fb4ac8b1f6f872f603a3b005ce8d000de989cd926ab7ba52c1",
    ),
    "LICENSE.txt": (
        "package/LICENSE.txt",
        "bee1fb9d9c97d42c12c22332c5250f2fb1ef5c2321f6f82beb23e3b77be50a29",
    ),
}


def verifier_local(dossier: Path = DOSSIER) -> list[str]:
    erreurs = []
    presents = {f.name for f in dossier.iterdir() if f.is_file()}
    for nom in sorted(presents - EMPREINTES.keys()):
        erreurs.append(f"{nom} : fichier non référencé")
    for nom, (_, attendu) in EMPREINTES.items():
        chemin = dossier / nom
        if not chemin.is_file():
            erreurs.append(f"{nom} : absent")
        elif hashlib.sha256(chemin.read_bytes()).hexdigest() != attendu:
            erreurs.append(f"{nom} : empreinte SHA-256 différente")
    return erreurs


def verifier_source(dossier: Path = DOSSIER) -> list[str]:
    url = f"https://registry.npmjs.org/altcha/-/altcha-{VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=60) as reponse:
        archive = reponse.read()
    integrite = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode()
    if integrite != INTEGRITE_NPM:
        return [f"paquet npm {VERSION} : intégrité sha512 différente de celle figée"]
    erreurs = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tgz:
        for nom, (chemin_npm, _) in EMPREINTES.items():
            membre = tgz.extractfile(chemin_npm)
            if membre is None or membre.read() != (dossier / nom).read_bytes():
                erreurs.append(f"{nom} : différent de {chemin_npm} du paquet npm")
    return erreurs


def main(arguments: list[str]) -> int:
    erreurs = verifier_local()
    if not erreurs and "--source" in arguments:
        erreurs = verifier_source()
    for erreur in erreurs:
        print(f"ÉCHEC {erreur}", file=sys.stderr)
    if not erreurs:
        print(f"ALTCHA {VERSION} : fichiers conformes")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
