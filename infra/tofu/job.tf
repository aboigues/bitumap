# Job de lot (002 T081, contracts/lot-job.md) : toutes les 15 min, 3 h au plus. Sans témoin
# de demande, il s'arrête sans ouvrir la base (T096). Les secrets sont lus dans Secret
# Manager au lancement (références), jamais copiés dans la définition du job.
locals {
  url_base_job = format("postgresql://%s:%s@%s", local.id_job.application_id,
  urlencode(local.cle_job), local.hote_base)
}

resource "scaleway_secret" "url_base_job" {
  name        = "bitumap-url-base-job"
  description = "URL de la base du job (application bitumap-job)"
  tags        = ["bitumap", "tofu"]
}

resource "scaleway_secret_version" "url_base_job" {
  secret_id = scaleway_secret.url_base_job.id
  data      = local.url_base_job
}

resource "scaleway_job_definition" "lot" {
  name                   = "lot"
  description            = "Lot de rapports (python -m bitumap.lot)"
  image_uri              = "${scaleway_registry_namespace.bitumap.endpoint}/job@${var.digest_job}"
  cpu_limit              = 2000
  memory_limit           = 4096
  local_storage_capacity = 10000 # cache éphémère des sources ; Scaleway : ]1000, 10240[ Mio (LL-024)
  timeout                = "3h"

  cron {
    schedule = "*/15 * * * *"
    timezone = "Europe/Paris"
  }

  env = merge(local.env_commun, {
    BITUMAP_S3_CLE_ACCES = local.id_job.access_key
  })

  secret_reference {
    secret_id      = scaleway_secret.url_base_job.id
    secret_version = scaleway_secret_version.url_base_job.revision
    environment    = "BITUMAP_DB_URL"
  }

  dynamic "secret_reference" {
    # Une seule clé IAM par composant (contracts/configuration.md).
    for_each = toset(["BITUMAP_S3_CLE_SECRETE", "BITUMAP_TEM_CLE", "BITUMAP_GENAI_CLE"])
    content {
      secret_id      = data.scaleway_secret_version.cle_job.secret_id
      secret_version = data.scaleway_secret_version.cle_job.revision
      environment    = secret_reference.value
    }
  }
}
