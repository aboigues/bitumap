"""Tout script versionné commençant par « #! » porte le bit d'exécution dans git (LL-015).

Sous /mnt/c (WSL), tous les fichiers paraissent exécutables : un script en 100644 y marche,
mais pas dans un clone Linux natif ni en CI, où le hook de protection de main (principe IX)
serait alors silencieusement inactif.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def _fichiers_suivis() -> list[tuple[str, str]]:
    sortie = subprocess.run(
        [shutil.which("git") or "git", "ls-files", "-s", "-z"],
        cwd=RACINE,
        capture_output=True,
        check=True,
    ).stdout.decode()
    lignes = [ligne for ligne in sortie.split("\0") if ligne]
    return [(ligne.split(" ", 1)[0], ligne.split("\t", 1)[1]) for ligne in lignes]


def test_scripts_executables():
    fautifs = []
    for mode, chemin in _fichiers_suivis():
        fichier = RACINE / chemin
        if mode != "100644" or not fichier.is_file():
            continue
        with fichier.open("rb") as f:
            if f.read(2) == b"#!":
                fautifs.append(chemin)
    assert fautifs == [], f"bit d'exécution manquant (git update-index --chmod=+x) : {fautifs}"


def test_hook_de_protection_de_main_executable():
    modes = dict((c, m) for m, c in _fichiers_suivis())
    assert modes[".claude/hooks/guard-main.sh"] == "100755"
