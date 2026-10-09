# Conteneur de l'API (002 T080) : 0 instance au repos (principe II), 2 au plus. Image
# désignée par son digest (notes de la version GitHub) : un tag ne fige pas le contenu.
resource "scaleway_container_namespace" "bitumap" {
  name        = "bitumap"
  description = "Services de bitumap"
}

locals {
  # URL de la base d'un composant : identifiant = application IAM, mot de passe = sa clé
  # secrète (Serverless SQL Database), point d'accès de la base.
  hote_base = trimprefix(scaleway_sdb_sql_database.bitumap.endpoint, "postgres://")
  url_base_api = format("postgresql://%s:%s@%s", local.id_api.application_id,
  urlencode(local.cle_api), local.hote_base)

  # Réglages communs à l'API et au job (contracts/configuration.md).
  env_commun = merge({
    BITUMAP_BUCKET_RAPPORTS  = scaleway_object_bucket.rapports.name
    BITUMAP_BUCKET_CACHE     = scaleway_object_bucket.cache.name
    BITUMAP_BUCKET_TERRAIN   = scaleway_object_bucket.terrain.name
    BITUMAP_URL_PUBLIQUE     = local.url_publique
    BITUMAP_COURRIEL_MODE    = "tem"
    BITUMAP_EMAIL_EXPEDITEUR = "ne-pas-repondre@${var.domaine_envoi}"
    BITUMAP_PROJET_SCALEWAY  = scaleway_sdb_sql_database.bitumap.project_id
    }, var.email_mainteneur == "" ? {} : {
    BITUMAP_EMAIL_MAINTENEUR = var.email_mainteneur
  })
}

resource "scaleway_container" "api" {
  name         = "api"
  namespace_id = scaleway_container_namespace.bitumap.id
  image        = "${scaleway_registry_namespace.bitumap.endpoint}/api@${var.digest_api}"
  port         = 8080
  min_scale    = 0
  max_scale    = 2
  cpu_limit    = 560
  timeout      = 60
  privacy      = "public"

  memory_limit_bytes     = 1024 * 1000 * 1000 # Scaleway compte en Mo décimaux (sinon écart à chaque plan)
  https_connections_only = true               # cookies __Host- : HTTPS seulement

  liveness_probe {
    http {
      path = "/health"
    }
    failure_threshold = 3
    interval          = "10s"
    timeout           = "3s"
  }

  environment_variables = merge(local.env_commun, {
    # Derrière le proxy de Scaleway : l'origine est la dernière adresse de X-Forwarded-For
    # (à vérifier après le premier déploiement, quickstart §6).
    BITUMAP_ORIGINE_VIA_PROXY = "true"
    BITUMAP_S3_CLE_ACCES      = local.id_api.access_key
    }, {
    # Identité de l'éditeur (mentions légales, issue #57) : valeurs non vides seulement.
    for cle, valeur in var.editeur : "BITUMAP_EDITEUR_${upper(cle)}" => valeur if valeur != ""
  })

  # Pas de référence à Secret Manager pour un conteneur (fournisseur 2.84) : les valeurs
  # passent par l'état, qui est chiffré.
  secret_environment_variables = {
    BITUMAP_DB_URL         = local.url_base_api
    BITUMAP_ALTCHA_HMAC    = random_password.altcha_hmac.result
    BITUMAP_SEL_ORIGINE    = random_password.sel_origine.result
    BITUMAP_S3_CLE_SECRETE = local.cle_api
    BITUMAP_TEM_CLE        = local.cle_api
  }
}

# Domaine du service : Scaleway vérifie le CNAME à la création, d'où activer_domaine
# (deuxième apply, après création du CNAME chez le registraire).
locals {
  hote_api = trimprefix(scaleway_container.api.public_endpoint, "https://")
}

resource "scaleway_container_domain" "service" {
  count        = var.activer_domaine ? 1 : 0
  container_id = scaleway_container.api.id
  hostname     = var.domaine_service
}
