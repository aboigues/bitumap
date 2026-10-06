#!/usr/bin/env bash
# Écrit ~/.config/bitumap/etat-tofu (mode 600) : identifiants du backend S3 d'OpenTofu, tirés
# du profil scw « bitumap » (application bitumap-tofu). Rien n'est affiché. À relancer après
# une rotation de la clé de bitumap-tofu.
set -euo pipefail
trap 'printf "[identifiants-etat] ÉCHEC ligne %s : %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR
set -o errtrace

fichier="$HOME/.config/bitumap/etat-tofu"
cle_acces=$(scw -p bitumap config get access-key)
cle_secrete=$(scw -p bitumap config get secret-key)
[ -n "$cle_acces" ] && [ -n "$cle_secrete" ] || {
  echo "[identifiants-etat] profil scw « bitumap » sans clé : lancer d'abord le bootstrap" >&2
  exit 1
}
mkdir -p "$(dirname "$fichier")"
chmod 700 "$(dirname "$fichier")"
( umask 077
  printf '[bitumap]\naws_access_key_id = %s\naws_secret_access_key = %s\n' \
    "$cle_acces" "$cle_secrete" >"$fichier" )
chmod 600 "$fichier"
echo "[identifiants-etat] $fichier écrit (mode 600)" >&2
