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
- Toute PR qui touche une page : actions humaines « essai des interfaces par le mainteneur
  avant fusion », avec les pages à essayer ; environnement : `scripts/essai/lancer.sh` (LL-031).

## Scaleway

- Projet `BITUMAP`, région `fr-par`. Profil scw pour OpenTofu et les commandes courantes :
  `scw -p bitumap` (droits limités au projet). Le profil d'administration (nom non versionné) ne sert
  qu'à `infra/bootstrap/bootstrap.sh`, lancé par un humain.
- Aucune ressource créée à la main : tout passe par OpenTofu (constitution).
- Variables d'environnement et secrets déclarés sur Scaleway : jamais de nom commençant par
  `SCW` (préfixe réservé à Scaleway) ; utiliser `BITUMAP_` / `bitumap-`
  (`specs/002-on-demand-report/contracts/configuration.md`).

## Sécurité CI

- Contrôles requis sur `main` (noms de jobs) : `analyze (actions)`, `dependency-review`,
  `secrets`, `vulnerabilities-iac`, `workflows-audit`, `exceptions`. Détail :
  `specs/001-security-ci-baseline/contracts/required-checks.md`.
- Avant de pousser un workflow : zizmor (`.github/zizmor.yml`) et actionlint en local, via
  Docker, avec les images de `.github/scanners/` ; conteneurs lancés avec `--user` (non root).
- Actions : SHA complet + tag en commentaire ; uniquement `actions/*` et `github/*`.
- Ajouter une exception = dans la **même PR** : entrée `.security/exceptions.toml` (≤ 90 j)
  + ligne dans `.trivyignore`, `.gitleaksignore` ou `.security/allowed-ghsas.txt` ;
  `python3 scripts/security/check_exceptions.py` doit passer.
