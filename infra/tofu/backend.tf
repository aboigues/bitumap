# Bucket d'état créé par infra/bootstrap/bootstrap.sh (privé, versionné) ; verrou par fichier
# dans le bucket (use_lockfile). Identifiants : AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY
# tirés du profil scw « bitumap » (README).
terraform {
  backend "s3" {
    bucket       = var.bucket_etat
    key          = "bitumap.tfstate"
    region       = "fr-par"
    use_lockfile = true
    endpoints = {
      s3 = "https://s3.fr-par.scw.cloud"
    }
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }
}
