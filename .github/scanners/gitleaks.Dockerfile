# Épinglage de l'image gitleaks par digest (constitution, principe I ; research R1).
# Ce fichier n'est jamais construit : les workflows lisent la ligne FROM et lancent
# l'image officielle par son digest. Dependabot (écosystème docker) propose ses mises à jour.
FROM zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
# Jamais construit ; les workflows lancent de toute façon l'image avec --user (non root).
USER 65532:65532
# Outil lancé une seule fois puis arrêté : aucune sonde de santé pertinente.
HEALTHCHECK NONE
