# Versions vérifiées le 2026-10-05 (dernières stables) : OpenTofu 1.13.1, Scaleway 2.84.0,
# random 3.9.1.
terraform {
  required_version = "~> 1.13.1"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.84.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9.1"
    }
  }

  # État et plans chiffrés (constitution, « Contraintes techniques ») : clé dérivée d'une
  # phrase secrète fournie par TF_VAR_phrase_chiffrement, jamais versionnée.
  encryption {
    key_provider "pbkdf2" "phrase" {
      passphrase = var.phrase_chiffrement
    }
    method "aes_gcm" "etat" {
      keys = key_provider.pbkdf2.phrase
    }
    state {
      method   = method.aes_gcm.etat
      enforced = true
    }
    plan {
      method   = method.aes_gcm.etat
      enforced = true
    }
  }
}

provider "scaleway" {
  # Identifiants : profil scw « bitumap » (~/.config/scw/config.yaml), jamais dans le dépôt.
  profile = "bitumap"
  region  = "fr-par"
  zone    = "fr-par-1"
}
