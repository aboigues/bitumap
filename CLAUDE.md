# bitumap

Plateforme Forward Deployed Engineering de diagnostic des chaussées (risque d'orniérage des
enrobés sur le réseau bus), générée à la demande pour un territoire d'Île-de-France.
Prototype de référence : `docs/reference/prototype-courbevoie-v2.html`.

## À lire en début de session

- Constitution (fait foi) : `.specify/memory/constitution.md`
- Retours d'expérience, à appliquer avant toute action :

@LESSON-LEARNED.md

## Règles de travail

- Documentation et échanges en français.
- Flux Spec Kit : `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-implement`.
- Principe IX : ne jamais commiter ni pousser sur `main` ; travailler sur une branche dédiée,
  ouvrir une PR, ne jamais l'approuver ni la fusionner. Verrouillé par
  `.claude/settings.json` et `.claude/hooks/guard-main.sh`.
- Principe VIII : tout bug ou incident rencontré ajoute une entrée à `LESSON-LEARNED.md`.
- Dépendances : vérifier la dernière version stable avant tout ajout.

## Scaleway

- Projet `BITUMAP`, région `fr-par`. Profil scw pour OpenTofu et les commandes courantes :
  `scw -p bitumap` (droits limités au projet). Le profil `telemach` (administration) ne sert
  qu'à `infra/bootstrap/bootstrap.sh`, lancé par un humain.
- Aucune ressource créée à la main : tout passe par OpenTofu (constitution).
