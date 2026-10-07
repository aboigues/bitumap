# Registre privé des images api et job (002 T078) ; 0,027 €/Go/mois. Les anciennes images
# ne sont pas encore purgées (à ajouter au workflow de publication).
resource "scaleway_registry_namespace" "bitumap" {
  name        = "bitumap"
  description = "Images de bitumap (api, job)"
  is_public   = false
}
