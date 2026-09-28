"""Configuration du service (contracts/configuration.md).

Toutes les valeurs viennent de variables d'environnement préfixées ``BITUMAP_``. Les secrets
sont des ``SecretStr`` : ils ne sont jamais affichés ni journalisés.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BITUMAP_", extra="ignore")

    # Quotas (FR-005)
    quota_generation_compte_jour: int = 5
    quota_generation_global_jour: int = 50
    quota_lien_email_heure: int = 3
    quota_lien_origine_heure: int = 10
    quota_defi_origine_heure: int = 60

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
    ia_plafond_jour_eur: Decimal = Decimal("20")
    alerte_mensuelle_eur: Decimal = Decimal("5")

    # Cache et sources (FR-008, FR-015)
    cache_rapport_jours: int = 30
    panoramax_rayon_m: int = 30

    # Stockage objet
    bucket_rapports: str = "bitumap-rapports"
    bucket_cache: str = "bitumap-cache"
    s3_endpoint: str = "https://s3.fr-par.scw.cloud"
    s3_region: str = "fr-par"

    # Courriel (FR-028) : « console » en local, « tem » en production
    courriel_mode: str = "console"
    email_expediteur: str = "ne-pas-repondre@localhost"
    email_mainteneur: str | None = None  # fourni par OpenTofu, jamais versionné
    url_publique: str = "http://127.0.0.1:8000"
    projet_scaleway: str = ""  # identifiant du projet BITUMAP (fourni par OpenTofu)

    # Secrets (Secret Manager en production, jamais dans le dépôt)
    db_url: SecretStr = SecretStr("postgresql://bitumap:bitumap-local@127.0.0.1:55432/bitumap")
    altcha_hmac: SecretStr = SecretStr("cle-de-developpement-uniquement")
    sel_origine: SecretStr = SecretStr("sel-de-developpement-uniquement")
    s3_cle_acces: SecretStr | None = None
    s3_cle_secrete: SecretStr | None = None
    tem_cle: SecretStr | None = None
    genai_cle: SecretStr | None = None

    # Cookies : « Secure » obligatoire hors développement local
    cookies_securises: bool = True


@lru_cache
def reglages() -> Reglages:
    return Reglages()
