# Envoi des e-mails (002 T082, FR-028) : Transactional Email sur un domaine propre, distinct
# du domaine du service (le CNAME du service ne cohabite pas avec SPF et MX). Les
# enregistrements DNS sont créés à la main chez le registraire (sortie « dns_courriel ») ;
# Scaleway vérifie le domaine ensuite, de lui-même (statut dans la sortie).
resource "scaleway_tem_domain" "envoi" {
  name       = var.domaine_envoi
  accept_tos = true # conditions de Transactional Email, acceptées par le mainteneur à l'apply
  autoconfig = false

  lifecycle {
    precondition {
      condition     = var.domaine_envoi != var.domaine_service
      error_message = "domaine_envoi doit différer de domaine_service (CNAME incompatible avec SPF et MX)."
    }
  }
}
