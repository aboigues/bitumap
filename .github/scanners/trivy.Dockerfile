# Épinglage de l'image trivy par digest (constitution, principe I ; research R1).
# Ce fichier n'est jamais construit : les workflows lisent la ligne FROM et lancent
# l'image officielle par son digest. Dependabot (écosystème docker) propose ses mises à jour.
FROM aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969
# Jamais construit ; les workflows lancent de toute façon l'image avec --user (non root).
USER 65532:65532
# Outil lancé une seule fois puis arrêté : aucune sonde de santé pertinente.
HEALTHCHECK NONE
