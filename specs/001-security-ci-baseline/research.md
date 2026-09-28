# Recherche (Phase 0) : Socle de sécurité CI

Versions vérifiées le 2026-09-28 via l'API GitHub et les registres de conteneurs.

## R1. Menace principale : la chaîne d'approvisionnement de la CI elle-même

- **Constat** : le 2026-03-19, `aquasecurity/trivy-action` (76 tags sur 77) et
  `aquasecurity/setup-trivy` (tous les tags) ont été réécrits vers un code voleur de secrets,
  après vol d'un jeton de publication
  ([avis GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23),
  [Microsoft](https://www.microsoft.com/en-us/security/blog/2026/03/24/detecting-investigating-defending-against-trivy-supply-chain-compromise/)).
  Les dépôts qui référençaient ces actions par **tag** ont exécuté le code malveillant ; ceux
  qui les épinglaient par **SHA de commit** n'ont pas été touchés.
- **Décision** :
  1. Actions GitHub : uniquement des actions **maintenues par GitHub** (`actions/*`,
     `github/codeql-action`), épinglées par SHA complet.
  2. Scanners tiers (Trivy, Gitleaks, zizmor) : **pas d'action tierce**. Ils sont exécutés
     depuis leur **image officielle épinglée par digest** `sha256`, sans jeton GitHub monté
     dans le conteneur.
  3. Les digests sont déclarés dans `.github/scanners/*.Dockerfile` (une ligne `FROM`), ce
     qui permet à Dependabot (écosystème `docker`) de proposer leurs mises à jour ; le
     workflow lit l'image depuis ce fichier.
- **Alternatives écartées** : `trivy-action` et `gitleaks-action` épinglées par SHA
  (surface plus large, jeton exposé à du JavaScript tiers ; `gitleaks-action` exige en plus
  une licence si le dépôt passe dans une organisation) ; `step-security/harden-runner`
  (utile mais service tiers supplémentaire, à réévaluer quand des secrets de déploiement
  existeront).

## R2. Analyse statique du code (FR-001)

- **Décision** : CodeQL en **configuration avancée** (workflow versionné), langage `actions`
  dès maintenant (analyse des workflows eux-mêmes), `python` ajouté quand du code Python
  existera. Requêtes `security-extended`.
- **Blocage** : CodeQL n'échoue pas de lui-même ; le blocage se fait par la règle
  **« code scanning »** du ruleset de `main` (seuil sécurité : `high_or_higher`,
  alertes : `errors`).
- **Alternatives** : configuration par défaut (« Default setup ») : rapide mais non
  versionnée et non relue par PR (contraire au principe IX) ; Semgrep : redondant à ce stade.
- **Version** : `github/codeql-action` v4.38.2 → `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2`.

## R3. Dépendances (FR-002, FR-007, FR-008)

- **Décision** :
  - PR : `actions/dependency-review-action` v5.0.0
    (`a1d282b36b6f3519aa1f3fc636f609c47dddb294`), `fail-on-severity: high`.
  - Continu : Trivy en mode `fs` (vulnérabilités des fichiers de dépendances), chaque semaine
    sur `main` et sur chaque PR.
  - Mises à jour : Dependabot (`.github/dependabot.yml`), écosystèmes `github-actions` et
    `docker` en mensuel groupé ; alertes et mises à jour de sécurité activées côté dépôt
    (action humaine, **activées le 2026-09-28**). Écosystèmes Python et `opentofu`
    (pris en charge par Dependabot depuis décembre 2025) ajoutés avec les premiers fichiers
    correspondants.
  - Le `dependabot.yml` actuel (modèle GitHub des PR #3/#4, `package-ecosystem: ""`) est
    invalide et sera remplacé.
- **Alternatives** : OSV-Scanner : bon outil, mais doublon de Trivy déjà retenu pour
  l'infrastructure et le SBOM (principe VII : un outil de moins).

## R4. Secrets (FR-003)

- **Décision** : deux couches.
  1. Côté plateforme : recherche de secrets et protection au push (déjà actives).
  2. Côté CI : Gitleaks v8.30.1 en conteneur
     (`zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`),
     sur l'historique complet (`fetch-depth: 0`), sortie SARIF avec secrets masqués
     (`--redact`).
- **Alternatives** : TruffleHog : orienté secrets « vérifiés » (appels réseau aux
  fournisseurs), moins adapté à un blocage déterministe.

## R5. Images et infrastructure (FR-004, FR-011)

- **Décision** : Trivy v0.74.0
  (`aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`,
  même digest sur `ghcr.io/aquasecurity/trivy`), scanners `vuln,misconfig`,
  `--severity HIGH,CRITICAL --exit-code 1`, plus une passe non bloquante toutes gravités en
  SARIF. Un dépôt sans cible produit un résultat vide et réussit (scénario US3-3).
  Les images de conteneur sont analysées **sur chaque PR et push** (constitution, principe I)
  dès qu'un `Dockerfile` applicatif existe : construction locale sans publication puis
  `trivy image` ; et à nouveau dans le workflow de livraison.
- **Note** : version postérieure à l'incident R1 et exécutée par digest ; la version
  compromise (v0.69.4) est hors de portée.

## R6. SBOM (FR-010)

- **Décision** : Trivy `--format cyclonedx` (format standard OWASP), généré dans le workflow
  de livraison **avant** la création de la version, puis attaché à la version par `gh release
  create`. Pas d'outil supplémentaire (Syft écarté pour la même raison que OSV-Scanner).

## R7. Durcissement des workflows (FR-012 à FR-014)

- **Décision** : zizmor v1.30.1 en conteneur
  (`ghcr.io/zizmorcore/zizmor@sha256:a2eb396d886c053073405c7a980f2139ba2248ec172243cfa3841e57196e8101`),
  mode `--pedantic` limité aux règles `unpinned-uses`, `excessive-permissions`,
  `template-injection`, `dangerous-triggers`, `artipacked`. Échec bloquant sur toute
  détection, quelle que soit sa gravité (exception à FR-005 au titre de FR-014), exécution
  `--offline`. Complété par la requête CodeQL `actions`.
- **Limite connue** : sur `pull_request`, GitHub exécute les workflows de la PR ; une PR peut
  donc neutraliser un contrôle. Parade : relecture humaine obligatoire des zones sensibles,
  rendue visible par le job informatif `sensitive-paths`. Les « required workflows » exécutés
  depuis `main` n'existent que pour les rulesets d'organisation.
- `permissions: {}` au niveau de chaque workflow, permissions accordées job par job.
- `persist-credentials: false` sur chaque `actions/checkout`.
- Déclencheurs : `pull_request` (jamais `pull_request_target`), `push` sur `main`,
  `schedule` hebdomadaire, `workflow_dispatch`.

## R8. Exceptions (FR-015)

- **Décision** : registre unique `.security/exceptions.toml` (lisible par `tomllib`, sans
  dépendance) et validateur `scripts/security/check_exceptions.py` (bibliothèque standard
  Python uniquement), exécuté comme contrôle requis. Il échoue si une exception est expirée,
  dépasse 90 jours, manque d'un champ, ou si un fichier d'ignorance d'outil (`.trivyignore`,
  `.gitleaksignore`, `.security/allowed-ghsas.txt`) contient une entrée absente du registre.
  La liste `allow-ghsas` de dependency-review est lue depuis ce dernier fichier : une
  exception expirée redevient donc bloquante automatiquement.
- Les alertes CodeQL ignorées le sont dans l'interface avec un commentaire obligatoire
  renvoyant à l'identifiant du registre (vérification manuelle mensuelle, documentée dans le
  quickstart).

## R9. Environnement d'exécution

- **Décision** : `runs-on: ubuntu-26.04`, image disponible en production depuis
  septembre 2026 ; `ubuntu-latest` basculera vers 26.04 entre le 19 octobre et le
  19 novembre 2026
  ([changelog GitHub](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/)).
  Épingler la version évite une bascule silencieuse. Python 3 et Docker sont fournis par
  l'image.
- `actions/checkout` v7.0.1 → `3d3c42e5aac5ba805825da76410c181273ba90b1`.
- `actions/upload-artifact` v7.0.1 → `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.
- `actions/download-artifact` v8.0.1 → `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`.

## R10. Gouvernance GitHub (actions humaines, principe IX)

- Activer : alertes Dependabot, mises à jour de sécurité Dependabot. La recherche de secrets
  et la protection au push sont déjà actives.
- Ruleset `ProtectTheMain` : cibler **uniquement** la branche par défaut (aujourd'hui `~ALL`,
  ce qui bloque aussi les branches de travail), ajouter les contrôles requis et la règle
  « code scanning » listés dans [contracts/required-checks.md](contracts/required-checks.md).
