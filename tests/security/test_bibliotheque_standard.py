"""Les tests de ce dossier n'importent que la bibliothèque standard (LL-033).

Le job « exceptions » (contrôle requis) les lance par « python3 -m unittest » sans installer
les dépendances du projet ; un test qui a besoin de pytest ou d'une bibliothèque tierce va
dans tests/unit, lancé par le job « tests ».
"""

import ast
import sys
import unittest
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent


def modules_importes(fichier):
    arbre = ast.parse(fichier.read_text(), filename=str(fichier))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            yield from (alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
            yield noeud.module.split(".")[0]


class BibliothequeStandard(unittest.TestCase):
    def test_aucune_dependance_tierce(self):
        for fichier in sorted(DOSSIER.glob("*.py")):
            tiers = sorted(set(modules_importes(fichier)) - sys.stdlib_module_names)
            with self.subTest(fichier=fichier.name):
                self.assertEqual(
                    tiers, [], f"{fichier.name} : bibliothèque standard seulement (job exceptions)"
                )


if __name__ == "__main__":
    unittest.main()
