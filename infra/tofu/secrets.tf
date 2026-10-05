# Secrets générés (002 T079, contracts/configuration.md). Les clés IAM d'exécution sont
# écrites par le bootstrap (« bitumap-cle-… ») ; l'URL de la base de chaque composant sera
# composée avec le conteneur et le job (PR B). Valeurs dans l'état, qui est chiffré.
resource "random_password" "altcha_hmac" {
  length  = 64
  special = false
}

resource "random_password" "sel_origine" {
  length  = 64
  special = false
}

resource "scaleway_secret" "altcha_hmac" {
  name        = "bitumap-altcha-hmac"
  description = "Clé HMAC des défis ALTCHA (API)"
  tags        = ["bitumap", "tofu"]
}

resource "scaleway_secret_version" "altcha_hmac" {
  secret_id = scaleway_secret.altcha_hmac.id
  data      = random_password.altcha_hmac.result
}

resource "scaleway_secret" "sel_origine" {
  name        = "bitumap-sel-origine"
  description = "Sel des empreintes d'adresse IP (API)"
  tags        = ["bitumap", "tofu"]
}

resource "scaleway_secret_version" "sel_origine" {
  secret_id = scaleway_secret.sel_origine.id
  data      = random_password.sel_origine.result
}
