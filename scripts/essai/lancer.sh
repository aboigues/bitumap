#!/usr/bin/env bash
# Essai local des interfaces par le mainteneur, avant fusion (LL-031).
#
# Base et stockage simulé de docker compose, rapport figé de Courbevoie, serveur sur
# http://127.0.0.1:8000. Connexion : lien affiché dans la console (courriels en mode console).
# Compte mainteneur : mainteneur@exemple.fr ; tout autre adresse est un agent.
#
# Usage : scripts/essai/lancer.sh [port]
set -Eeuo pipefail
trap 'echo "lancer.sh : échec ligne $LINENO : $BASH_COMMAND" >&2' ERR

racine="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$racine"
port="${1:-8000}"

port_s3="$(grep '^BITUMAP_S3_PORT=' .env | cut -d= -f2)"
[ -n "$port_s3" ] || { echo "BITUMAP_S3_PORT absent de .env" >&2; exit 1; }

export UV_PYTHON_PREFERENCE=only-managed
export BITUMAP_S3_ENDPOINT="http://127.0.0.1:$port_s3"
export BITUMAP_S3_CLE_ACCES=essai BITUMAP_S3_CLE_SECRETE=essai BITUMAP_S3_REGION=us-east-1
export BITUMAP_EMAIL_MAINTENEUR="mainteneur@exemple.fr"
export BITUMAP_URL_PUBLIQUE="http://127.0.0.1:$port"

docker compose up -d --wait db s3
uv run python scripts/essai/preparer.py
echo "Essai : http://127.0.0.1:$port (Ctrl+C pour arrêter)"
exec uv run uvicorn bitumap.api:app --host 127.0.0.1 --port "$port" \
  --log-config scripts/essai/journal.json
