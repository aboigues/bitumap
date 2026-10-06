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
