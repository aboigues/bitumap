# Valeurs dans terraform.tfvars (non versionné, modèle : terraform.tfvars.example) ou en
# variables d'environnement TF_VAR_… ; aucune n'a de valeur par défaut propre au mainteneur.

variable "bucket_etat" {
  description = "Bucket d'état OpenTofu (sortie « state_bucket » du bootstrap)."
  type        = string

  # Évaluée au plan seulement : OpenTofu configure le backend avant de valider les variables
  # (d'où tofu init -input=false et le contrôle d'identifiants-etat.sh, LL-021).
  validation {
    condition     = can(regex("^bitumap-tofu-state-[0-9a-f]{8}$", var.bucket_etat))
    error_message = "Bucket d'état invalide : attendu bitumap-tofu-state-<8 caractères hexadécimaux> (sortie « state_bucket » du bootstrap, dans terraform.tfvars)."
  }
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

  # Seul principal autorisé à administrer les buckets (stockage.tf) : un identifiant faux
  # enfermerait OpenTofu hors des buckets dès l'apply (LL-021).
  validation {
    condition = (
      can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.application_tofu))
      && var.application_tofu != "00000000-0000-0000-0000-000000000000"
    )
    error_message = "application_tofu invalide : identifiant de l'application IAM bitumap-tofu (sortie « application_id » du bootstrap ; console : Organisation > IAM > Applications), pas celui du projet."
  }
}

variable "domaine_service" {
  description = "Nom de domaine du service (ex. bitumap.exemple.fr), sans schéma : URL publique et CORS de l'envoi des photos."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.domaine_service))
    error_message = "Nom de domaine invalide (minuscules, sans schéma ni chemin)."
  }
}

variable "autoriser_destruction" {
  description = "Vrai seulement pour détruire l'infrastructure : autorise la suppression des buckets non vides (rapports, cache, photos, toutes versions). Irréversible."
  type        = bool
  default     = false
}
