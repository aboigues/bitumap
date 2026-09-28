"""Applique les migrations SQL de ``db/migrations`` dans l'ordre (idempotent)."""

from __future__ import annotations

from importlib import resources

import psycopg

from bitumap.config import reglages


def migrations() -> list[tuple[int, str, str]]:
    dossier = resources.files("bitumap.db") / "migrations"
    resultat = []
    for fichier in dossier.iterdir():
        if fichier.name.endswith(".sql"):
            numero = int(fichier.name.split("_", 1)[0])
            resultat.append((numero, fichier.name, fichier.read_text(encoding="utf-8")))
    return sorted(resultat)


def migrer(url: str | None = None) -> list[str]:
    """Applique les migrations manquantes ; renvoie les noms appliqués."""
    appliquees = []
    with psycopg.connect(url or reglages().db_url.get_secret_value()) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " numero integer PRIMARY KEY, nom text NOT NULL,"
            " appliquee_le timestamptz NOT NULL DEFAULT now())"
        )
        conn.execute("SELECT pg_advisory_xact_lock(4242)")  # une seule migration à la fois
        deja = {r[0] for r in conn.execute("SELECT numero FROM schema_version")}
        for numero, nom, sql in migrations():
            if numero in deja:
                continue
            conn.execute(sql)
            conn.execute("INSERT INTO schema_version (numero, nom) VALUES (%s, %s)", (numero, nom))
            appliquees.append(nom)
    return appliquees


def main() -> None:
    for nom in migrer():
        print(f"migration appliquée : {nom}")
    print("schéma à jour")


if __name__ == "__main__":
    main()
