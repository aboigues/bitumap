# Valeurs dans terraform.tfvars (non versionné, modèle : terraform.tfvars.example) ou en
# variables d'environnement TF_VAR_… ; aucune n'a de valeur par défaut propre au mainteneur.

variable "bucket_etat" {
  description = "Bucket d'état OpenTofu (sortie « state_bucket » du bootstrap)."
  type        = string
}

variable "phrase_chiffrement" {
  description = "Phrase secrète du chiffrement de l'état et des plans (TF_VAR_phrase_chiffrement)."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.phrase_chiffrement) >= 32
    error_message = "La phrase de chiffrement doit compter au moins 32 caractères."
  }
}

variable "application_tofu" {
  description = "Identifiant de l'application IAM bitumap-tofu (sortie « application_id » du bootstrap), seule à administrer les buckets."
  type        = string
}

variable "domaine_service" {
  description = "Nom de domaine du service (ex. bitumap.exemple.fr), sans schéma : URL publique et CORS de l'envoi des photos."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.domaine_service))
    error_message = "Nom de domaine invalide (minuscules, sans schéma ni chemin)."
  }
}
