# Épinglage de l'image zizmor par digest (constitution, principe I ; research R1).
# Ce fichier n'est jamais construit : les workflows lisent la ligne FROM et lancent
# l'image officielle par son digest. Dependabot (écosystème docker) propose ses mises à jour.
FROM ghcr.io/zizmorcore/zizmor:1.30.1@sha256:a2eb396d886c053073405c7a980f2139ba2248ec172243cfa3841e57196e8101
# Jamais construit ; les workflows lancent de toute façon l'image avec --user (non root).
USER 65532:65532
# Outil lancé une seule fois puis arrêté : aucune sonde de santé pertinente.
HEALTHCHECK NONE
