output "buckets" {
  description = "Noms des buckets (variables BITUMAP_BUCKET_… de l'application)."
  value = {
    rapports = scaleway_object_bucket.rapports.name
    cache    = scaleway_object_bucket.cache.name
    terrain  = scaleway_object_bucket.terrain.name
  }
}

output "base_point_acces" {
  description = "Point d'accès de la base (sans identifiants)."
  value       = scaleway_sdb_sql_database.bitumap.endpoint
}

output "registre" {
  description = "Adresse du registre (docker push)."
  value       = scaleway_registry_namespace.bitumap.endpoint
}

output "conteneur_api" {
  description = "Adresse native du conteneur de l'API (sans domaine personnalisé)."
  value       = "https://${local.hote_api}"
}

output "job_lot" {
  description = "Identifiant de la définition du job (scw jobs definition start …), sans la région."
  # L'identifiant OpenTofu est « fr-par/<uuid> » ; scw attend l'UUID seul.
  value = element(split("/", scaleway_job_definition.lot.id), 1)
}

output "dns_service" {
  description = "Enregistrement à créer chez le registraire, puis activer_domaine = true."
  value = {
    nom    = var.domaine_service
    type   = "CNAME"
    valeur = "${local.hote_api}."
  }
}

output "dns_courriel" {
  description = "Enregistrements de l'envoi d'e-mails à créer chez le registraire (noms complets)."
  # Scaleway donne déjà des noms complets terminés par un point (dkim_name, dmarc_name,
  # mx_config) : ils sont repris tels quels, sans le point final (LL-025).
  value = [
    { nom = var.domaine_envoi, type = "TXT", valeur = scaleway_tem_domain.envoi.spf_value },
    { nom = trimsuffix(scaleway_tem_domain.envoi.dkim_name, "."), type = "TXT", valeur = scaleway_tem_domain.envoi.dkim_config },
    { nom = var.domaine_envoi, type = "MX", valeur = "${scaleway_tem_domain.envoi.mx_priority} ${scaleway_tem_domain.envoi.mx_config}" },
    { nom = trimsuffix(scaleway_tem_domain.envoi.dmarc_name, "."), type = "TXT", valeur = scaleway_tem_domain.envoi.dmarc_config },
  ]
}

output "courriel_statut" {
  description = "Statut du domaine d'envoi chez Scaleway (checked = vérifié ; relire après tofu refresh)."
  value       = scaleway_tem_domain.envoi.status
}
