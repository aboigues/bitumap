# Envoi des e-mails (002 T082, FR-028) : Transactional Email sur un domaine propre, distinct
# du domaine du service (le CNAME du service ne cohabite pas avec SPF et MX). Les
# enregistrements DNS sont créés à la main chez le registraire (sortie « dns_courriel ») ;
# Scaleway vérifie le domaine ensuite, de lui-même (statut dans la sortie).
# Abonnement souscrit par le bootstrap (le fournisseur ne sait que le lire) : lu dès le plan,
# pour échouer avant de créer quoi que ce soit s'il manque (LL-024).
data "scaleway_tem_offer_subscription" "projet" {
  project_id = scaleway_sdb_sql_database.bitumap.project_id
}

resource "scaleway_tem_domain" "envoi" {
  name       = var.domaine_envoi
  accept_tos = true # conditions de Transactional Email, acceptées par le mainteneur à l'apply
  autoconfig = false

  lifecycle {
    precondition {
      # Sans abonnement, la source renvoie null, pas une erreur.
      condition     = coalesce(data.scaleway_tem_offer_subscription.projet.offer_name, "aucune") != "aucune"
      error_message = "Aucune offre Transactional Email sur le projet : relancer infra/bootstrap/bootstrap.sh (étape 6)."
    }
    precondition {
      condition     = var.domaine_envoi != var.domaine_service
      error_message = "domaine_envoi doit différer de domaine_service (CNAME incompatible avec SPF et MX)."
    }
  }
}
