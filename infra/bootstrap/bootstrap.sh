#!/usr/bin/env bash
# Amorçage Scaleway de bitumap (constitution, principe III et « Contraintes techniques »).
#
# Crée, de façon idempotente, le socle que l'IaC OpenTofu ne peut pas créer elle-même :
#   1. le projet Scaleway BITUMAP (région fr-par) ;
#   2. l'application IAM « bitumap-tofu », limitée au projet BITUMAP ;
#   3. sa clé API, enregistrée directement dans le profil scw « bitumap » (jamais affichée) ;
#   4. le bucket d'état OpenTofu, privé et versionné.
#
# Toute autre ressource DOIT être décrite en OpenTofu.
# Usage : infra/bootstrap/bootstrap.sh            (ADMIN_PROFILE lu dans .env)
#         ADMIN_PROFILE=<profil-admin> infra/bootstrap/bootstrap.sh
# (profil scw local disposant des droits d'administration de l'organisation ; son nom
#  n'est volontairement pas versionné)
set -euo pipefail

# Lecture de ADMIN_PROFILE depuis .env s'il n'est pas déjà défini. Le fichier est lu comme
# des données (clé=valeur), jamais exécuté (pas de `source`).
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.env"
if [ -z "${ADMIN_PROFILE:-}" ] && [ -f "$ENV_FILE" ]; then
  ADMIN_PROFILE=$(sed -n 's/^ADMIN_PROFILE=\([A-Za-z0-9_-]*\)[[:space:]]*$/\1/p' "$ENV_FILE" | tail -1)
fi
ADMIN_PROFILE="${ADMIN_PROFILE:?à définir dans .env ou en variable : profil scw local, droits admin sur organisation Scaleway}"
PROJECT_NAME="BITUMAP"
APP_NAME="bitumap-tofu"
POLICY_NAME="bitumap-tofu-project"
TARGET_PROFILE="bitumap"
REGION="fr-par"
ZONE="fr-par-1"
KEY_TTL_DAYS=180
# Droits limités au projet BITUMAP ; l'IAM elle-même reste gérée par ce script (profil admin).
PERMISSION_SETS=(
  ContainerRegistryFullAccess
  ContainersFullAccess
  ServerlessJobsFullAccess
  ObjectStorageFullAccess
  SecretManagerFullAccess
  ObservabilityFullAccess
)

admin() { scw -p "$ADMIN_PROFILE" "$@"; }
log() { printf '[bootstrap] %s\n' "$*" >&2; }
# Aucun arrêt silencieux (LL-001) : toute erreur indique la ligne et la commande en cause.
trap 'log "ÉCHEC ligne $LINENO : $BASH_COMMAND"' ERR
set -o errtrace

org_id=$(admin config get default-organization-id)

# 1. Projet
project_id=$(admin account project list name="$PROJECT_NAME" -o json | jq -r --arg n "$PROJECT_NAME" '.[] | select(.name==$n) | .id' | head -1)
if [ -z "$project_id" ]; then
  project_id=$(admin account project create name="$PROJECT_NAME" \
    description="bitumap : diagnostic orniérage à la demande (github.com/aboigues/bitumap)" -o json | jq -r .id)
  log "projet $PROJECT_NAME créé ($project_id)"
else
  log "projet $PROJECT_NAME déjà présent ($project_id)"
fi

# 2. Application IAM + politique
app_id=$(admin iam application list name="$APP_NAME" -o json | jq -r --arg n "$APP_NAME" '.[] | select(.name==$n) | .id' | head -1)
if [ -z "$app_id" ]; then
  app_id=$(admin iam application create name="$APP_NAME" \
    description="OpenTofu et CI de bitumap, limitée au projet BITUMAP" -o json | jq -r .id)
  log "application $APP_NAME créée ($app_id)"
else
  log "application $APP_NAME déjà présente ($app_id)"
fi

if [ -z "$(admin iam policy list policy-name="$POLICY_NAME" -o json | jq -r '.[].id' | head -1)" ]; then
  args=(name="$POLICY_NAME" application-id="$app_id"
        description="Droits de $APP_NAME, limités au projet $PROJECT_NAME"
        rules.0.project-ids.0="$project_id")
  for i in "${!PERMISSION_SETS[@]}"; do args+=("rules.0.permission-set-names.$i=${PERMISSION_SETS[$i]}"); done
  admin iam policy create "${args[@]}" -o json >/dev/null
  log "politique $POLICY_NAME créée"
else
  log "politique $POLICY_NAME déjà présente (non modifiée)"
fi

# 3. Clé API → profil scw local (secret jamais affiché)
if scw -p "$TARGET_PROFILE" config get access-key >/dev/null 2>&1 && \
   [ -n "$(scw -p "$TARGET_PROFILE" config get access-key 2>/dev/null)" ]; then
  log "profil scw $TARGET_PROFILE déjà configuré (clé non régénérée)"
else
  expires=$(date -u -d "+${KEY_TTL_DAYS} days" +%Y-%m-%dT%H:%M:%SZ)
  key_json=$(admin iam api-key create application-id="$app_id" default-project-id="$project_id" \
    expires-at="$expires" description="bitumap-tofu, poste local, expire $expires" -o json)
  scw -p "$TARGET_PROFILE" config set \
    access-key="$(jq -r .access_key <<<"$key_json")" \
    secret-key="$(jq -r .secret_key <<<"$key_json")" \
    default-organization-id="$org_id" default-project-id="$project_id" \
    default-region="$REGION" default-zone="$ZONE" >/dev/null
  unset key_json
  log "clé API créée (expire le $expires) et enregistrée dans le profil scw $TARGET_PROFILE"
fi

# 4. Bucket d'état OpenTofu (créé avec les droits de l'application, donc dans le projet BITUMAP)
bucket=$(scw -p "$TARGET_PROFILE" object bucket list region="$REGION" -o json 2>/dev/null \
  | jq -r '.[] | select((.Name // .name)|startswith("bitumap-tofu-state-")) | (.Name // .name)' | head -1)
if [ -z "$bucket" ]; then
  bucket="bitumap-tofu-state-$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  for attempt in 1 2 3 4 5 6; do   # propagation IAM : la politique peut mettre quelques secondes
    if scw -p "$TARGET_PROFILE" object bucket create name="$bucket" region="$REGION" \
         enable-versioning=true acl=private tags.0=bitumap tags.1=tofu-state -o json >/dev/null 2>&1; then
      break
    fi
    [ "$attempt" = 6 ] && { log "échec de création du bucket $bucket"; exit 1; }
    sleep 10
  done
  log "bucket d'état $bucket créé (privé, versionné)"
else
  log "bucket d'état $bucket déjà présent"
fi

jq -n --arg project_id "$project_id" --arg app_id "$app_id" --arg bucket "$bucket" \
  --arg region "$REGION" --arg profile "$TARGET_PROFILE" \
  '{project_id:$project_id, application_id:$app_id, state_bucket:$bucket, region:$region, scw_profile:$profile}'
