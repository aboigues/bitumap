# Registre privé des images api et job (002 T078) ; 0,027 €/Go/mois. Les anciennes images
# sont supprimées par le workflow de publication (PR C).
resource "scaleway_registry_namespace" "bitumap" {
  name        = "bitumap"
  description = "Images de bitumap (api, job)"
  is_public   = false
}
