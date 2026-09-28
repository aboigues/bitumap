# Contrat : contrôles requis sur `main`

Ces noms sont un **contrat stable** : le ruleset de `main` les référence. Renommer un job
impose de mettre à jour le ruleset dans la même PR (action humaine, principe IX).

## Contrôles de statut requis

Dans le ruleset, GitHub attend le **nom du job** (colonne « Nom à saisir »), pas le nom
affiché `workflow / job`.

| Nom affiché (check) | Nom à saisir dans le ruleset | Workflow | Déclencheurs | Échec si |
|---|---|---|---|---|
| `codeql / analyze (actions)` | `analyze (actions)` | `codeql.yml` | PR, push `main`, hebdo | analyse en erreur (le blocage des alertes passe par la règle *code scanning* ci-dessous) |
| `security / dependency-review` | `dependency-review` | `security.yml` | PR | dépendance ajoutée avec vulnérabilité ≥ high, ou licence interdite |
| `security / secrets` | `secrets` | `security.yml` | PR, push `main`, hebdo | secret détecté par Gitleaks non couvert par une exception active |
| `security / vulnerabilities-iac` | `vulnerabilities-iac` | `security.yml` | PR, push `main`, hebdo | Trivy `vuln,misconfig` ≥ HIGH (dépôt, et images construites depuis chaque `Dockerfile` applicatif) non couvert par une exception active |
| `security / workflows-audit` | `workflows-audit` | `security.yml` | PR, push `main`, hebdo | zizmor, **toute gravité** (exception FR-005 / FR-014) : action non épinglée, permissions excessives, injection, déclencheur dangereux, identifiants persistés |
| `security / exceptions` | `exceptions` | `security.yml` | PR, push `main`, hebdo (+ quotidien) | registre invalide, exception expirée ou > 90 j, ignore orphelin |

Remarque : `security / dependency-review` n'existe que sur les PR ; il n'est pas exécuté sur
push et n'y bloque donc rien, ce qui est le comportement attendu.

Contrôle **informatif, non requis** : `security / sensitive-paths` (commentaire listant les
fichiers de zones sensibles modifiés). Il ne peut pas être requis : sur une PR, il s'exécute
depuis la version de la PR et ne protège donc pas contre une PR qui le modifie.

## Règle « code scanning » du ruleset

| Outil | Seuil alertes de sécurité | Seuil alertes |
|---|---|---|
| `CodeQL` | `high_or_higher` | `errors` |
| `zizmor` | `high_or_higher` | `errors` |

## Autres règles du ruleset (rappel)

- Cible : **branche par défaut uniquement** (`~DEFAULT_BRANCH`).
- PR obligatoire ; interdiction du force-push et de la suppression ; aucun contournement.
- Option recommandée : « Require branches to be up to date before merging ».

## Workflow de livraison (`release.yml`) — hors ruleset

Déclenché par un tag `v*.*.*` poussé par le mainteneur :

1. `release / scan` : Trivy ≥ HIGH bloquant sur le commit tagué (et sur l'image si un
   Dockerfile applicatif existe).
2. `release / sbom` : SBOM CycloneDX.
3. `release / publish` : crée la version GitHub et attache le SBOM, **seulement si** 1 et 2
   ont réussi. Seul job disposant de `contents: write`.
