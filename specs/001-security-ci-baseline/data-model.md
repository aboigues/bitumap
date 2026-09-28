# Modèle de données : Socle de sécurité CI

Pas de base de données : les entités sont des fichiers du dépôt ou des objets GitHub.

## Constat de sécurité (Finding)

Objet GitHub « code scanning alert » (SARIF) ou alerte Dependabot / secret scanning.

| Champ | Description |
|---|---|
| `tool` | `CodeQL`, `Trivy`, `Gitleaks`, `zizmor`, `dependency-review`, `Dependabot` |
| `rule_id` | identifiant de règle ou de vulnérabilité (CVE, GHSA, id Gitleaks) |
| `severity` | `critical`, `high`, `medium`, `low` (normalisée) |
| `location` | fichier, ligne ; ou manifeste + paquet + version |
| `state` | `open` → `fixed` ou `dismissed` (exception) |

Règle : `severity ∈ {critical, high}` et `state = open` ⇒ contrôle en échec (FR-005).

## Exception

Entrée de `.security/exceptions.toml` ; format dans
[contracts/exceptions-registry.md](contracts/exceptions-registry.md).

| Champ | Obligatoire | Validation |
|---|---|---|
| `id` | oui | unique, forme `EXC-NNN` |
| `tool` | oui | `trivy`, `gitleaks`, `codeql`, `dependency-review` |
| `finding` | oui | identifiant du constat (CVE, GHSA, empreinte Gitleaks, id d'alerte) |
| `reason` | oui | non vide ; faux positif ou atténuation décrite |
| `owner` | oui | identifiant GitHub |
| `created` | oui | date ISO, ≤ aujourd'hui |
| `expires` | oui | date ISO, > `created`, `expires − created ≤ 90 j` |

États : `active` (aujourd'hui < `expires`) → `expired` (le contrôle échoue jusqu'au
renouvellement motivé ou à la suppression).

Cohérence : chaque entrée de `.trivyignore` / `.gitleaksignore` / `.security/allowed-ghsas.txt` DOIT correspondre à une
exception `active` du même outil ; inversement une exception sans entrée d'ignorance n'est
qu'un avertissement.

## Contrôle requis (Required check)

| Champ | Description |
|---|---|
| `name` | nom du job tel qu'affiché par GitHub (contrat stable) |
| `workflow` | fichier de workflow |
| `triggers` | événements déclencheurs |
| `blocking_rule` | condition d'échec |

Liste normative : [contracts/required-checks.md](contracts/required-checks.md).

## SBOM

Fichier CycloneDX JSON `bitumap-<version>.cdx.json`, attaché à la version GitHub
correspondante ; généré à partir du commit tagué.

## Zone sensible (CODEOWNERS)

| Chemin | Raison |
|---|---|
| `/.github/` | workflows, Dependabot, CODEOWNERS (principes I, IX) |
| `/.claude/`, `/CLAUDE.md` | garde-fous des agents (principe IX) |
| `/.specify/memory/` | constitution |
| `/.security/`, `/SECURITY.md`, `/.trivyignore`, `/.gitleaksignore` | exceptions et politique |
| `/scripts/security/` | validateur |
| `/LESSON-LEARNED.md` | retours d'expérience (principe VIII) |
| méthode de score (chemin défini par la feature correspondante) | principe IV |
