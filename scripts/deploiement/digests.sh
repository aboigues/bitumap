#!/usr/bin/env bash
# Report des digests d'une version dans infra/tofu/terraform.tfvars, après vérification.
#
# Contrôles, dans l'ordre ; le moindre écart arrête le script sans rien modifier :
#   1. version GitHub publiée (pas un brouillon) et commit désigné par son tag ;
#   2. workflow release de ce tag terminé en succès, sur ce commit ;
#   3. digests des notes de version = digests du tag dans le registre Scaleway ;
#   4. attestation de provenance de chaque image : signée par release.yml de ce dépôt, à
#      partir de ce tag et de ce commit, sur un exécuteur hébergé par GitHub.
# Puis seules les lignes digest_api et digest_job de terraform.tfvars sont remplacées
# (copie dans terraform.tfvars.sauvegarde). Ni plan ni apply : ils restent au mainteneur.
#
# Prérequis : gh connecté, profil scw « bitumap », connexion Docker au registre
# (scw -p bitumap registry login).
#
# Usage : scripts/deploiement/digests.sh vX.Y.Z [--sans-attestation]
#   --sans-attestation : versions publiées avant les attestations (v0.1.0 à v0.1.2) seulement.
set -Eeuo pipefail
trap 'echo "digests.sh : échec ligne $LINENO : $BASH_COMMAND" >&2' ERR

# Versions publiées avant l'ajout des attestations au workflow release : aucune autre ne
# peut être déployée sans vérification de provenance.
VERSIONS_SANS_ATTESTATION="v0.1.0 v0.1.1 v0.1.2"

erreur() { echo "ERREUR : $*" >&2; exit 1; }
etape() { echo "• $*"; }

usage="usage : $0 vX.Y.Z [--sans-attestation]"
{ [ $# -ge 1 ] && [ $# -le 2 ]; } || erreur "$usage"
tag="$1"
sans_attestation=false
if [ $# = 2 ]; then
  [ "$2" = --sans-attestation ] || erreur "$usage"
  sans_attestation=true
fi
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || erreur "version attendue sous la forme vX.Y.Z, reçu « $tag »"
if $sans_attestation && [[ " $VERSIONS_SANS_ATTESTATION " != *" $tag "* ]]; then
  erreur "--sans-attestation refusé pour $tag : réservé à $VERSIONS_SANS_ATTESTATION"
fi

for outil in gh jq scw; do
  command -v "$outil" >/dev/null || erreur "outil absent : $outil"
done

racine="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$racine"
tfvars="${BITUMAP_TFVARS:-$racine/infra/tofu/terraform.tfvars}"
profil="${BITUMAP_SCW_PROFIL:-bitumap}"
[ -f "$tfvars" ] || erreur "$tfvars absent (modèle : infra/tofu/terraform.tfvars.example)"
for nom in api job; do
  [ "$(grep -cE "^digest_${nom}[[:space:]]*=" "$tfvars")" = 1 ] \
    || erreur "une et une seule ligne digest_${nom} attendue dans $tfvars"
done

depot="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo "Dépôt : $depot ; version : $tag ; profil scw : $profil"

# 1. Version et commit du tag
etape "version GitHub $tag"
version="$(gh release view "$tag" --repo "$depot" --json isDraft,body)"
[ "$(jq -r .isDraft <<<"$version")" = false ] || erreur "la version $tag est un brouillon"
ref="$(gh api "repos/$depot/git/ref/tags/$tag")"
commit="$(jq -r .object.sha <<<"$ref")"
if [ "$(jq -r .object.type <<<"$ref")" = tag ]; then   # tag annoté : objet tag → commit
  commit="$(gh api "repos/$depot/git/tags/$commit" -q .object.sha)"
fi
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || erreur "commit du tag $tag illisible"
echo "  commit du tag : $commit"

# 2. Workflow release du tag
etape "workflow release du tag"
execution="$(gh run list --repo "$depot" --workflow release.yml --branch "$tag" --event push \
  --limit 1 --json conclusion,headSha,databaseId -q '.[0] // empty')"
[ -n "$execution" ] || erreur "aucune exécution du workflow release pour $tag"
[ "$(jq -r .conclusion <<<"$execution")" = success ] \
  || erreur "workflow release de $tag non réussi ($(jq -r .conclusion <<<"$execution"))"
[ "$(jq -r .headSha <<<"$execution")" = "$commit" ] \
  || erreur "workflow release lancé sur un autre commit que celui du tag"

# 3. Notes de version et registre
etape "digests des notes de version et du registre Scaleway"
espace="$(scw -p "$profil" registry namespace list name=bitumap -o json \
  | jq -c '[.[] | select(.name == "bitumap")]')"
[ "$(jq length <<<"$espace")" = 1 ] || erreur "espace de registre « bitumap » introuvable (profil $profil)"
espace_id="$(jq -r '.[0].id' <<<"$espace")"
endpoint="$(jq -r '.[0].endpoint' <<<"$espace")"
declare -A digest
for nom in api job; do
  mapfile -t lus < <(jq -r .body <<<"$version" \
    | grep -E "^- ${nom} : " | grep -oE 'sha256:[0-9a-f]{64}' || true)
  [ "${#lus[@]}" = 1 ] || erreur "un et un seul digest « ${nom} » attendu dans les notes de $tag"
  if [[ "${lus[0]}" =~ ^sha256:0+$ ]]; then erreur "digest ${nom} nul dans les notes de $tag"; fi
  image_id="$(scw -p "$profil" registry image list namespace-id="$espace_id" name="$nom" -o json \
    | jq -r --arg n "$nom" '[.[] | select(.name == $n)] | if length == 1 then .[0].id else empty end')"
  [ -n "$image_id" ] || erreur "image « ${nom} » introuvable dans le registre"
  registre="$(scw -p "$profil" registry tag list image-id="$image_id" name="$tag" -o json \
    | jq -r --arg t "$tag" '[.[] | select(.name == $t and .status == "ready")]
                            | if length == 1 then .[0].digest else empty end')"
  [ -n "$registre" ] || erreur "tag $tag de l'image « ${nom} » absent du registre ou pas prêt"
  [ "$registre" = "${lus[0]}" ] \
    || erreur "digest ${nom} divergent : notes ${lus[0]}, registre $registre"
  digest[$nom]="${lus[0]}"
  echo "  ${nom} : ${digest[$nom]}"
done

# 4. Provenance
if $sans_attestation; then
  echo "ATTENTION : provenance NON vérifiée ($tag est antérieure aux attestations)." >&2
else
  for nom in api job; do
    etape "attestation de provenance de « ${nom} »"
    gh attestation verify "oci://${endpoint}/${nom}@${digest[$nom]}" \
      --repo "$depot" \
      --signer-workflow "github.com/${depot}/.github/workflows/release.yml" \
      --source-ref "refs/tags/${tag}" \
      --source-digest "$commit" \
      --deny-self-hosted-runners >/dev/null \
      || erreur "provenance de « ${nom} » non vérifiée : attestation absente ou invalide (image illisible : scw -p $profil registry login)"
  done
fi

# Remplacement des deux lignes, droits du fichier conservés (il contient des secrets :
# seules les lignes de digests sont affichées).
if grep -qxF "digest_api = \"${digest[api]}\"" "$tfvars" \
  && grep -qxF "digest_job = \"${digest[job]}\"" "$tfvars"; then
  echo "terraform.tfvars déjà à jour pour $tag : rien à modifier."
  exit 0
fi
avant="$(grep -E '^digest_(api|job)[[:space:]]*=' "$tfvars")"
cp -p "$tfvars" "$tfvars.sauvegarde"
temporaire="$(mktemp "$tfvars.XXXXXX")"
trap 'rm -f "$temporaire"' EXIT
sed -E \
  -e "s|^digest_api[[:space:]]*=.*$|digest_api = \"${digest[api]}\"|" \
  -e "s|^digest_job[[:space:]]*=.*$|digest_job = \"${digest[job]}\"|" \
  "$tfvars" >"$temporaire"
cat "$temporaire" >"$tfvars"
echo
echo "terraform.tfvars mis à jour (copie : $(basename "$tfvars").sauvegarde)"
echo "Avant :"; sed 's/^/  /' <<<"$avant"
echo "Après :"; grep -E '^digest_(api|job)[[:space:]]*=' "$tfvars" | sed 's/^/  /'
echo
echo "Suite (mainteneur) : tofu plan -input=false, apply, puis un second plan qui doit être vide."
