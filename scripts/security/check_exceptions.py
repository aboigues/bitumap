#!/usr/bin/env python3
"""Validateur du registre d'exceptions de sécurité (constitution, principe I ; spec FR-015).

Contrat : specs/001-security-ci-baseline/contracts/exceptions-registry.md
Bibliothèque standard uniquement.

Codes retour : 0 registre valide, 1 au moins une erreur, 2 fichier illisible ou TOML invalide.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import tomllib
from pathlib import Path

TOOLS = {"trivy", "gitleaks", "codeql", "dependency-review"}
REQUIRED = ("id", "tool", "finding", "reason", "owner", "created", "expires")
ID_PATTERN = re.compile(r"^EXC-\d{3}$")
MAX_DAYS = 90


def parse_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def read_lines(path: Path):
    """Lignes utiles d'un fichier d'ignorance (sans commentaires ni lignes vides)."""
    if not path.is_file():
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def validate(registry: dict, root: Path, today: dt.date):
    errors, warnings = [], []
    entries = registry.get("exception", [])
    if not isinstance(entries, list):
        return [("registre", "la clé « exception » doit être un tableau [[exception]]")], warnings

    active = {tool: {} for tool in TOOLS}  # outil -> {finding: expires}
    seen_ids = set()

    for index, entry in enumerate(entries, start=1):
        label = str(entry.get("id") or f"entrée n°{index}")
        missing = [f for f in REQUIRED if entry.get(f) in (None, "")]
        for field in missing:
            errors.append((label, f"champ manquant ou vide : {field}"))

        exc_id = entry.get("id")
        if exc_id:
            if not ID_PATTERN.match(str(exc_id)):
                errors.append((label, "identifiant hors format EXC-NNN"))
            if exc_id in seen_ids:
                errors.append((label, "identifiant dupliqué"))
            seen_ids.add(exc_id)

        tool = entry.get("tool")
        if tool and tool not in TOOLS:
            errors.append((label, f"outil inconnu « {tool} »"))

        created = parse_date(entry.get("created")) if "created" not in missing else None
        expires = parse_date(entry.get("expires")) if "expires" not in missing else None
        if "created" not in missing and created is None:
            errors.append((label, "date created invalide"))
        if "expires" not in missing and expires is None:
            errors.append((label, "date expires invalide"))
        if created and created > today:
            errors.append((label, f"created {created} est dans le futur"))
        if created and expires:
            duration = (expires - created).days
            if duration <= 0:
                errors.append((label, "expires doit être postérieure à created"))
            elif duration > MAX_DAYS:
                errors.append((label, f"durée de {duration} jours (maximum {MAX_DAYS})"))
        if expires and expires <= today:
            errors.append((label, f"exception expirée le {expires}"))

        entry_ok = not missing and tool in TOOLS and expires and expires > today
        if entry_ok:
            active[tool][str(entry["finding"])] = expires

    # Contrôle croisé avec les fichiers d'ignorance des outils.
    for line in read_lines(root / ".trivyignore"):
        parts = line.split()
        finding = parts[0]
        exp = next((p[4:] for p in parts[1:] if p.startswith("exp:")), None)
        if finding not in active["trivy"]:
            errors.append((".trivyignore", f"{finding} sans exception trivy active"))
        elif exp is None:
            errors.append((".trivyignore", f"{finding} sans date exp:AAAA-MM-JJ"))
        elif exp != active["trivy"][finding].isoformat():
            errors.append(
                (
                    ".trivyignore",
                    f"{finding} exp:{exp} ≠ expires {active['trivy'][finding].isoformat()}",
                )
            )

    for line in read_lines(root / ".gitleaksignore"):
        if line not in active["gitleaks"]:
            errors.append((".gitleaksignore", f"{line} sans exception gitleaks active"))

    ghsas = read_lines(root / ".security" / "allowed-ghsas.txt")
    for line in ghsas:
        if line not in active["dependency-review"]:
            errors.append(
                (
                    ".security/allowed-ghsas.txt",
                    f"{line} sans exception dependency-review active",
                )
            )

    # Exception active jamais utilisée : sans effet, donc simple avertissement (data-model.md).
    declared = {
        "trivy": {line.split()[0] for line in read_lines(root / ".trivyignore")},
        "gitleaks": set(read_lines(root / ".gitleaksignore")),
        "dependency-review": set(ghsas),
    }
    for tool, used in declared.items():
        for finding in active[tool]:
            if finding not in used:
                message = f"exception {tool} active mais absente du fichier d'ignorance"
                warnings.append((finding, message))

    return errors, warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=".security/exceptions.toml", type=Path)
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args(argv)

    try:
        with args.registry.open("rb") as handle:
            registry = tomllib.load(handle)
    except FileNotFoundError:
        print(f"ERREUR registre: fichier introuvable : {args.registry}", file=sys.stderr)
        return 2
    except tomllib.TOMLDecodeError as exc:
        print(f"ERREUR registre: TOML invalide : {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(registry, args.root, args.today)
    for label, message in errors:
        print(f"ERREUR {label}: {message}", file=sys.stderr)
    for label, message in warnings:
        print(f"AVERTISSEMENT {label}: {message}", file=sys.stderr)
    if errors:
        return 1
    count = len(registry.get("exception", []))
    print(f"Registre valide : {count} exception(s) active(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
