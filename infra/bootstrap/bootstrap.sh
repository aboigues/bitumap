#!/usr/bin/env bash
# Amorçage Scaleway de bitumap (constitution, principe III et « Contraintes techniques »).
#
# Crée, de façon idempotente, le socle que l'IaC OpenTofu ne peut pas créer elle-même :
#   1. le projet Scaleway BITUMAP (région fr-par) ;
#   2. l'application IAM « bitumap-tofu », limitée au projet BITUMAP ;
#   3. sa clé API, enregistrée directement dans le profil scw « bitumap » (jamais affichée) ;
#   4. le bucket d'état OpenTofu, privé et versionné ;
#   5. les applications IAM d'exécution « bitumap-api » et « bitumap-job » (clés écrites
#      directement dans Secret Manager) et « bitumap-ci » (clé écrite directement dans les
#      secrets GitHub du dépôt) : aucune clé n'est jamais affichée.
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
RUNTIME_KEY_TTL_DAYS=365   # clés d'exécution et de CI : rotation documentée dans le README
GITHUB_REPO="aboigues/bitumap"
# Droits limités au projet BITUMAP ; l'IAM elle-même reste gérée par ce script (profil admin).
PERMISSION_SETS=(
  ContainerRegistryFullAccess
  ContainersFullAccess
  ServerlessJobsFullAccess
  ObjectStorageFullAccess
  SecretManagerFullAccess
  ObservabilityFullAccess
  ServerlessSQLDatabaseFullAccess
  TransactionalEmailFullAccess
)
# Applications d'exécution (moindre privilège, plan « Complexity Tracking ») : la
# restriction par bucket est faite par les politiques de bucket d'OpenTofu (stockage.tf).
API_PERMISSION_SETS=(
  ServerlessSQLDatabaseDataReadWrite   # données seulement, pas la structure des tables
  ObjectStorageBucketsRead             # liste des versions (retrait RGPD d'une photo)
  ObjectStorageObjectsRead
  ObjectStorageObjectsWrite
  ObjectStorageObjectsDelete
  TransactionalEmailEmailApiCreate
)
JOB_PERMISSION_SETS=(
  ServerlessSQLDatabaseReadWrite       # applique les migrations du schéma
  ObjectStorageBucketsRead
  ObjectStorageObjectsRead
  ObjectStorageObjectsWrite
  ObjectStorageObjectsDelete
  TransactionalEmailEmailApiCreate
  GenerativeApisModelAccess
)
CI_PERMISSION_SETS=(
  ContainerRegistryFullAccess          # publication des images (aucun jeu plus étroit)
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

# Politique d'une application : créée, ou ses règles remplacées par la liste du script
# (idempotent : relancer applique la liste courante).
ensure_policy() {
  local name=$1 application=$2; shift 2
  local rules=(rules.0.project-ids.0="$project_id") i=0 set policy_id
  for set in "$@"; do rules+=("rules.0.permission-set-names.$i=$set"); i=$((i + 1)); done
  policy_id=$(admin iam policy list policy-name="$name" -o json | jq -r '.[].id' | head -1)
  if [ -z "$policy_id" ]; then
    admin iam policy create name="$name" application-id="$application" \
      description="Droits de l'application, limités au projet $PROJECT_NAME" "${rules[@]}" -o json >/dev/null
    log "politique $name créée"
  else
    admin iam rule update "$policy_id" "${rules[@]}" -o json >/dev/null
    log "politique $name déjà présente (règles à jour)"
  fi
}

ensure_policy "$POLICY_NAME" "$app_id" "${PERMISSION_SETS[@]}"

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

# 5. Applications d'exécution et de CI
ensure_app() {
  local name=$1 description=$2 id
  id=$(admin iam application list name="$name" -o json | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' | head -1)
  if [ -z "$id" ]; then
    id=$(admin iam application create name="$name" description="$description" -o json | jq -r .id)
    log "application $name créée ($id)"
  else
    log "application $name déjà présente ($id)"
  fi
  printf '%s' "$id"
}

new_key() {   # JSON de la clé sur la sortie standard, jamais affiché par l'appelant
  local application=$1 name=$2 expires
  expires=$(date -u -d "+${RUNTIME_KEY_TTL_DAYS} days" +%Y-%m-%dT%H:%M:%SZ)
  admin iam api-key create application-id="$application" default-project-id="$project_id" \
    expires-at="$expires" description="$name, expire $expires" -o json
}

secret_id() {
  admin secret secret list name="$1" project-id="$project_id" region="$REGION" -o json \
    | jq -r --arg n "$1" '.[] | select(.name==$n) | .id' | head -1
}

secret_has_version() {
  [ "$(admin secret version list "$1" status.0=enabled region="$REGION" -o json | jq 'length')" -gt 0 ]
}

# Écrit une valeur dans un secret (créé au besoin) ; la valeur passe par un fichier
# temporaire en mode 600, jamais par la ligne de commande ni la sortie.
write_secret() {
  local name=$1 description=$2 value=$3 id tmp
  id=$(secret_id "$name")
  if [ -z "$id" ]; then
    id=$(admin secret secret create name="$name" project-id="$project_id" region="$REGION" \
      description="$description" tags.0=bitumap tags.1=bootstrap -o json | jq -r .id)
  fi
  tmp=$(mktemp); chmod 600 "$tmp"
  printf '%s' "$value" >"$tmp"
  admin secret version create "$id" data=@"$tmp" disable-previous=true region="$REGION" -o json >/dev/null
  rm -f "$tmp"
}

# Clé d'exécution : secret « bitumap-cle-<composant> » (clé secrète seule, injectée telle
# quelle) et « bitumap-id-<composant> » (identifiants publics : application, clé d'accès,
# lus par OpenTofu). Une clé existante n'est jamais régénérée.
ensure_runtime_app() {
  local component=$1; shift
  local name="bitumap-$component" id key_json cle
  id=$(ensure_app "$name" "Exécution bitumap ($component), limitée au projet BITUMAP")
  ensure_policy "$name-project" "$id" "$@"
  cle=$(secret_id "bitumap-cle-$component")
  if [ -n "$cle" ] && secret_has_version "$cle"; then
    log "clé de $name déjà dans Secret Manager (non régénérée)"
    return
  fi
  key_json=$(new_key "$id" "$name")
  write_secret "bitumap-cle-$component" "Clé secrète IAM de $name (bootstrap)" \
    "$(jq -r .secret_key <<<"$key_json")"
  write_secret "bitumap-id-$component" "Identifiants publics de $name (bootstrap)" \
    "$(jq -c '{application_id, access_key}' <<<"$key_json")"
  unset key_json
  log "clé de $name créée et écrite dans Secret Manager"
}

ensure_runtime_app api "${API_PERMISSION_SETS[@]}"
ensure_runtime_app job "${JOB_PERMISSION_SETS[@]}"

# CI : clé écrite dans les secrets GitHub du dépôt (gh lit la valeur sur l'entrée standard).
ci_id=$(ensure_app bitumap-ci "CI bitumap : publication des images, limitée au projet BITUMAP")
ensure_policy bitumap-ci-project "$ci_id" "${CI_PERMISSION_SETS[@]}"
if gh secret list --repo "$GITHUB_REPO" --json name -q '.[].name' | grep -qx BITUMAP_CI_CLE_SECRETE; then
  log "clé de bitumap-ci déjà dans les secrets GitHub (non régénérée)"
else
  key_json=$(new_key "$ci_id" bitumap-ci)
  jq -r .access_key <<<"$key_json" | gh secret set BITUMAP_CI_CLE_ACCES --repo "$GITHUB_REPO"
  jq -r .secret_key <<<"$key_json" | gh secret set BITUMAP_CI_CLE_SECRETE --repo "$GITHUB_REPO"
  unset key_json
  log "clé de bitumap-ci créée et écrite dans les secrets GitHub"
fi

jq -n --arg project_id "$project_id" --arg app_id "$app_id" --arg bucket "$bucket" \
  --arg region "$REGION" --arg profile "$TARGET_PROFILE" \
  '{project_id:$project_id, application_id:$app_id, state_bucket:$bucket, region:$region, scw_profile:$profile}'
