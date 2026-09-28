"""Accès à la base PostgreSQL (état vivant : comptes, sessions, quotas, file d'attente)."""

from bitumap.db.connexion import connexion, fermer_pool

__all__ = ["connexion", "fermer_pool"]
