"""Configuration du service (contracts/configuration.md).

Toutes les valeurs viennent de variables d'environnement préfixées ``BITUMAP_``. Les secrets
sont des ``SecretStr`` : ils ne sont jamais affichés ni journalisés.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    # En local, les valeurs viennent aussi de .env (non versionné) ; aucune valeur secrète par
    # défaut dans le code (revue de la PR #14).
    model_config = SettingsConfigDict(
        env_prefix="BITUMAP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Quotas (FR-005)
    quota_generation_compte_jour: int = 5
    quota_generation_global_jour: int = 50
    quota_lien_email_heure: int = 3
    quota_lien_origine_heure: int = 10
    quota_defi_origine_heure: int = 60

    # Antibot ALTCHA (research R5) : preuve de travail PBKDF2 résolue par le navigateur
    altcha_algorithme: str = "PBKDF2/SHA-256"
    altcha_cout: int = 5000
    altcha_validite_min: int = 10
    # Vrai derrière le proxy de Scaleway : l'origine est alors la dernière adresse de
    # X-Forwarded-For (ajoutée par le proxy, non falsifiable par le client).
    origine_via_proxy: bool = False

    # Connexion (FR-006, FR-027)
    lien_validite_min: int = 15
    session_jours: int = 7
    compte_inactif_mois: int = 12

    # Lots (FR-007a, FR-017)
    lot_taille: int = 10
    commune_delai_max_min: int = 30
    lot_delai_max_h: int = 3
    lot_intervalle_min: int = 15

    # IA (FR-014, FR-024, FR-029)
    ia_modele: str = "mistral-small-3.2-24b-instruct-2506"
    ia_version_prompt: str = "age_enrobe_v1"
    ia_url: str = "https://api.scaleway.ai/v1"
    ia_tarif_entree_eur_mtok: Decimal = Decimal("0.15")
    ia_tarif_sortie_eur_mtok: Decimal = Decimal("0.35")
    ia_plafond_rapport_eur: Decimal = Decimal("2")
    ia_plafond_jour_eur: Decimal = Decimal("5")
    alerte_mensuelle_eur: Decimal = Decimal("5")

    # Cache et sources (FR-008, FR-015)
    cache_rapport_jours: int = 30
    panoramax_rayon_m: int = 30

    # Méthode de score (004, contrat methode-v2 § 3) : la 1.2 reste en service tant que le
    # mainteneur n'a pas validé la 2.0 sur les relevés de 003 (FR-013).
    methode: Literal["1.2", "2.0"] = "1.2"
    ete_reference: int | None = None  # défaut : dernier été complet (score.methode)
    station_meteo: str = "75114001"  # Paris-Montsouris (research R4)

    # Stockage objet
    bucket_rapports: str = "bitumap-rapports"
    bucket_cache: str = "bitumap-cache"
    bucket_terrain: str = "bitumap-terrain"  # photos des relevés (003), privé et versionné

    # Relevés terrain (003, FR-003, FR-018)
    quota_releves_compte_jour: int = 200
    quota_photos_compte_jour: int = 1000
    photos_par_releve: int = 5
    photo_max_octets: int = 10 * 1024 * 1024
    photo_formulaire_validite_s: int = 300
    photos_max_go: float = 20.0
    s3_endpoint: str = "https://s3.fr-par.scw.cloud"
    s3_region: str = "fr-par"

    # Courriel (FR-028) : « console » en local, « tem » en production
    courriel_mode: str = "console"
    email_expediteur: str = "ne-pas-repondre@localhost"
    email_mainteneur: str | None = None  # fourni par OpenTofu, jamais versionné
    url_publique: str = "http://127.0.0.1:8000"
    projet_scaleway: str = ""  # identifiant du projet BITUMAP (fourni par OpenTofu)
    # security.txt (RFC 9116) : signalement privé, comme SECURITY.md
    contact_securite: str = "https://github.com/aboigues/bitumap/security/advisories/new"

    # Secrets (Secret Manager en production, jamais dans le dépôt)
    db_url: SecretStr
    altcha_hmac: SecretStr
    sel_origine: SecretStr
    s3_cle_acces: SecretStr | None = None
    s3_cle_secrete: SecretStr | None = None
    tem_cle: SecretStr | None = None
    genai_cle: SecretStr | None = None
    # Température de surface (004 R3) : compte EROS de l'USGS, jeton d'application M2M
    usgs_utilisateur: SecretStr | None = None
    usgs_jeton: SecretStr | None = None

    # Cookies : « Secure » obligatoire hors développement local
    cookies_securises: bool = True


@lru_cache
def reglages() -> Reglages:
    return Reglages()
