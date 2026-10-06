# Bucket d'état créé par infra/bootstrap/bootstrap.sh (privé, versionné) ; verrou par fichier
# dans le bucket (use_lockfile). Identifiants : fichier hors dépôt, mode 600, généré depuis le
# profil scw « bitumap » par identifiants-etat.sh (aucune variable d'environnement ; OpenTofu
# refuse des valeurs sensibles dans ce bloc, qu'il recopie dans .terraform/). Le format du
# fichier est celui qu'impose le protocole S3 du backend.
terraform {
  backend "s3" {
    bucket                   = var.bucket_etat
    key                      = "bitumap.tfstate"
    region                   = "fr-par"
    use_lockfile             = true
    shared_credentials_files = ["~/.config/bitumap/etat-tofu"]
    profile                  = "bitumap"
    endpoints = {
      s3 = "https://s3.fr-par.scw.cloud"
    }
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }
}
