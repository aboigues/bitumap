#!/usr/bin/env bash
# Démantèlement de bitumap sur Scaleway : défait, dans l'ordre inverse, ce que crée
# bootstrap.sh. À lancer APRÈS `tofu destroy` (infra/tofu/README.md, « Destruction ») : le
# script refuse de continuer tant qu'une ressource gérée par OpenTofu existe encore.
#
#   1. secrets GitHub de la CI ;
#   2. secrets « bitumap-cle-… » et « bitumap-id-… » de Secret Manager ;
#   3. applications bitumap-api, bitumap-job, bitumap-ci, leurs politiques (et leurs clés) ;
#   4. bucket d'état OpenTofu, vidé de toutes ses versions (l'état est perdu) ;
#   5. application bitumap-tofu, sa politique, la clé du profil scw « bitumap » et le
#      fichier d'identifiants du backend ;
#   6. le projet BITUMAP, s'il est vide.
#
# Usage : infra/bootstrap/demantelement.sh --simulation   (affiche les actions, ne fait rien)
#         infra/bootstrap/demantelement.sh                (demande la confirmation)
# ADMIN_PROFILE comme pour bootstrap.sh. Idempotent : relancé, il ignore ce qui n'existe plus.
# Prérequis : scw, jq, gh connecté (administration du dépôt), uv et l'environnement Python du
# dépôt (vidage du bucket versionné, que scw ne sait pas faire).
set -euo pipefail

SIMULATION=false
[ "${1:-}" = "--simulation" ] && SIMULATION=true

ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.env"
REPO_DIR="$(dirname "$ENV_FILE")"
if [ -z "${ADMIN_PROFILE:-}" ] && [ -f "$ENV_FILE" ]; then
  ADMIN_PROFILE=$(sed -n 's/^ADMIN_PROFILE=\([A-Za-z0-9_-]*\)[[:space:]]*$/\1/p' "$ENV_FILE" | tail -1)
fi
ADMIN_PROFILE="${ADMIN_PROFILE:?à définir dans .env ou en variable : profil scw local, droits admin sur organisation Scaleway}"
PROJECT_NAME="BITUMAP"
TARGET_PROFILE="bitumap"
REGION="fr-par"
GITHUB_REPO="aboigues/bitumap"
CONFIRMATION="DÉTRUIRE BITUMAP"

admin() { scw -p "$ADMIN_PROFILE" "$@"; }
tofu_scw() { scw -p "$TARGET_PROFILE" "$@"; }
log() { printf '[démantèlement] %s\n' "$*" >&2; }
trap 'log "ÉCHEC ligne $LINENO : $BASH_COMMAND"' ERR
set -o errtrace

# Action destructive : exécutée, ou seulement affichée en simulation.
faire() {
  if $SIMULATION; then
    log "(simulation) $*"
  else
    "$@"
  fi
}

project_id=$(admin account project list name="$PROJECT_NAME" -o json \
  | jq -r --arg n "$PROJECT_NAME" '.[] | select(.name==$n) | .id' | head -1)
if [ -z "$project_id" ]; then
  log "projet $PROJECT_NAME absent : rien à démanteler"
  exit 0
fi

# 0. Garde-fou : plus aucune ressource gérée par OpenTofu.
restes=()
tofu_ok=false
if [ -n "$(tofu_scw config get access-key 2>/dev/null || true)" ]; then
  tofu_ok=true
  while IFS= read -r b; do restes+=("bucket $b"); done < <(
    tofu_scw object bucket list region="$REGION" -o json \
      | jq -r '.[] | (.Name // .name) | select(startswith("bitumap-tofu-state-") | not)')
fi
while IFS= read -r r; do restes+=("$r"); done < <(
  admin registry namespace list project-id="$project_id" region="$REGION" -o json | jq -r '.[] | "registre " + .name'
  admin sdb-sql database list project-id="$project_id" region="$REGION" -o json | jq -r '.[] | "base " + .name'
  admin container namespace list project-id="$project_id" region="$REGION" -o json | jq -r '.[] | "conteneurs " + .name'
  admin jobs definition list project-id="$project_id" region="$REGION" -o json | jq -r '.[] | "job " + .name'
  admin secret secret list project-id="$project_id" region="$REGION" tags.0=tofu -o json | jq -r '.[] | "secret " + .name'
)
if [ "${#restes[@]}" -gt 0 ]; then
  log "ressources OpenTofu encore présentes : lancer d'abord tofu destroy (infra/tofu/README.md)"
  printf '  - %s\n' "${restes[@]}" >&2
  exit 1
fi

if ! $SIMULATION; then
  log "Tout ce que crée le bootstrap va être supprimé (projet $PROJECT_NAME compris). Irréversible."
  read -r -p "Tapez « $CONFIRMATION » pour confirmer : " reponse
  [ "$reponse" = "$CONFIRMATION" ] || { log "confirmation incorrecte : abandon"; exit 1; }
fi

# 1. Secrets GitHub de la CI
for nom in BITUMAP_CI_CLE_ACCES BITUMAP_CI_CLE_SECRETE; do
  if gh secret list --repo "$GITHUB_REPO" --json name -q '.[].name' | grep -qx "$nom"; then
    faire gh secret delete "$nom" --repo "$GITHUB_REPO"
    log "secret GitHub $nom supprimé"
  fi
done

# 2. Secrets écrits par le bootstrap
for nom in bitumap-cle-api bitumap-id-api bitumap-cle-job bitumap-id-job; do
  id=$(admin secret secret list name="$nom" project-id="$project_id" region="$REGION" -o json \
    | jq -r --arg n "$nom" '.[] | select(.name==$n) | .id' | head -1)
  if [ -n "$id" ]; then
    faire admin secret secret delete "$id" region="$REGION"
    log "secret $nom supprimé"
  fi
done

# Application et sa politique (la suppression de l'application révoque ses clés).
supprimer_app() {
  local name=$1 policy=$2 id
  id=$(admin iam policy list policy-name="$policy" -o json | jq -r '.[].id' | head -1)
  if [ -n "$id" ]; then
    faire admin iam policy delete "$id"
    log "politique $policy supprimée"
  fi
  id=$(admin iam application list name="$name" -o json \
    | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' | head -1)
  if [ -n "$id" ]; then
    faire admin iam application delete "$id"
    log "application $name supprimée (clés révoquées)"
  fi
}

# 3. Applications d'exécution et de CI
supprimer_app bitumap-api bitumap-api-project
supprimer_app bitumap-job bitumap-job-project
supprimer_app bitumap-ci bitumap-ci-project

# 4. Bucket d'état : vidé de toutes ses versions et marqueurs (Python du dépôt, boto3),
#    avec la clé du profil « bitumap » lue par le script lui-même (jamais affichée).
if $tofu_ok; then
  bucket=$(tofu_scw object bucket list region="$REGION" -o json \
    | jq -r '.[] | select((.Name // .name)|startswith("bitumap-tofu-state-")) | (.Name // .name)' | head -1)
  if [ -n "$bucket" ]; then
    if $SIMULATION; then
      log "(simulation) vider toutes les versions de $bucket, puis le supprimer"
    else
      (cd "$REPO_DIR" && uv run --no-sync python - "$bucket" "$TARGET_PROFILE" "$REGION" <<'PY'
import subprocess, sys
import boto3

bucket, profil, region = sys.argv[1:4]
cle = lambda nom: subprocess.run(
    ["scw", "-p", profil, "config", "get", nom], check=True, capture_output=True, text=True
).stdout.strip()
s3 = boto3.client(
    "s3", endpoint_url=f"https://s3.{region}.scw.cloud", region_name=region,
    aws_access_key_id=cle("access-key"), aws_secret_access_key=cle("secret-key"),
)
n = 0
for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
    objets = [{"Key": v["Key"], "VersionId": v["VersionId"]}
              for v in page.get("Versions", []) + page.get("DeleteMarkers", [])]
    if objets:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": objets, "Quiet": True})
        n += len(objets)
print(f"[démantèlement] {bucket} vidé ({n} versions et marqueurs)", file=sys.stderr)
PY
      )
      tofu_scw object bucket delete "$bucket" region="$REGION"
    fi
    log "bucket d'état $bucket supprimé"
  fi
fi

# 5. bitumap-tofu, clé du profil local et identifiants du backend
supprimer_app bitumap-tofu bitumap-tofu-project
if $tofu_ok; then
  faire scw -p "$TARGET_PROFILE" config unset access-key
  faire scw -p "$TARGET_PROFILE" config unset secret-key
  log "clé retirée du profil scw $TARGET_PROFILE"
fi
if [ -f "$HOME/.config/bitumap/etat-tofu" ]; then
  faire rm -f "$HOME/.config/bitumap/etat-tofu"
  log "fichier d'identifiants du backend supprimé"
fi

# 6. Projet (refusé par Scaleway s'il contient encore des ressources)
faire admin account project delete project-id="$project_id"
log "projet $PROJECT_NAME supprimé"
