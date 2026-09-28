"""Tests du validateur de registre d'exceptions (contracts/exceptions-registry.md).

Bibliothèque standard uniquement. Date injectée par --today pour des résultats reproductibles.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "security" / "check_exceptions.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TODAY = "2026-10-15"


def run(registry, root="root_empty", today=TODAY):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(FIXTURES / registry),
            "--root",
            str(FIXTURES / root),
            "--today",
            today,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stderr


class RegistreValide(unittest.TestCase):
    def test_registre_vide(self):
        self.assertEqual(run("empty.toml")[0], 0)

    def test_exception_active(self):
        self.assertEqual(run("valid.toml")[0], 0)

    def test_fichiers_ignorance_coherents(self):
        code, err = run("full.toml", root="root_valid")
        self.assertEqual(code, 0, err)


class RegistreInvalide(unittest.TestCase):
    def assert_erreur(self, registry, attendu, root="root_empty"):
        code, err = run(registry, root=root)
        self.assertEqual(code, 1, err)
        self.assertRegex(err, r"^ERREUR ", err)
        self.assertIn(attendu, err)

    def test_exception_expiree(self):
        self.assert_erreur("expired.toml", "EXC-001: exception expirée")

    def test_duree_superieure_a_90_jours(self):
        self.assert_erreur("too_long.toml", "EXC-001: durée de 91 jours")

    def test_champ_manquant(self):
        self.assert_erreur("missing_field.toml", "EXC-001: champ manquant ou vide : owner")

    def test_outil_inconnu(self):
        self.assert_erreur("bad_tool.toml", "EXC-001: outil inconnu « semgrep »")

    def test_identifiant_duplique(self):
        self.assert_erreur("duplicate_id.toml", "EXC-001: identifiant dupliqué")

    def test_trivyignore_orphelin(self):
        self.assert_erreur(
            "valid.toml", ".trivyignore: CVE-2026-9999 sans exception trivy active",
            root="root_orphan",
        )

    def test_date_exp_differente(self):
        self.assert_erreur(
            "valid.toml", ".trivyignore: CVE-2026-0001 exp:2026-11-30 ≠ expires 2026-10-31",
            root="root_exp_mismatch",
        )

    def test_ghsa_orphelin(self):
        self.assert_erreur(
            "valid.toml",
            ".security/allowed-ghsas.txt: GHSA-zzzz-zzzz-zzzz sans exception dependency-review active",
            root="root_ghsa_orphan",
        )

    def test_exception_expiree_rend_ignore_orphelin(self):
        # Une fois l'exception expirée, l'entrée .trivyignore redevient bloquante.
        code, err = run("full.toml", root="root_valid", today="2026-11-01")
        self.assertEqual(code, 1, err)
        self.assertIn(".trivyignore: CVE-2026-0001 sans exception trivy active", err)


class FichierIllisible(unittest.TestCase):
    def test_toml_invalide(self):
        self.assertEqual(run("invalid.toml")[0], 2)

    def test_registre_absent(self):
        self.assertEqual(run("absent.toml")[0], 2)


if __name__ == "__main__":
    unittest.main()
