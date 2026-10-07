# Applications d'exécution créées par le bootstrap (bitumap-tofu n'a aucun droit IAM) : leurs
# identifiants publics sont lus dans Secret Manager (secrets « bitumap-id-… »).
data "scaleway_secret_version" "id_api" {
  secret_name = "bitumap-id-api"
  revision    = "latest_enabled"
}

data "scaleway_secret_version" "id_job" {
  secret_name = "bitumap-id-job"
  revision    = "latest_enabled"
}

locals {
  id_api = jsondecode(base64decode(data.scaleway_secret_version.id_api.data))
  id_job = jsondecode(base64decode(data.scaleway_secret_version.id_job.data))

  principal_tofu = "application_id:${var.application_tofu}"
  principal_api  = "application_id:${nonsensitive(local.id_api.application_id)}"
  principal_job  = "application_id:${nonsensitive(local.id_job.application_id)}"

  url_publique = "https://${var.domaine_service}"
}

# Clés secrètes d'exécution (écrites par le bootstrap) : mot de passe de la base, stockage
# objet, envoi d'e-mails, IA. Le job les lit directement dans Secret Manager ; le conteneur
# les reçoit par OpenTofu (pas de référence de secret pour un conteneur).
data "scaleway_secret_version" "cle_api" {
  secret_name = "bitumap-cle-api"
  revision    = "latest_enabled"
}

data "scaleway_secret_version" "cle_job" {
  secret_name = "bitumap-cle-job"
  revision    = "latest_enabled"
}

locals {
  cle_api = base64decode(data.scaleway_secret_version.cle_api.data)
  cle_job = base64decode(data.scaleway_secret_version.cle_job.data)
}
