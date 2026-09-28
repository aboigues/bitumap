# Quickstart : valider le socle de sécurité CI

## Prérequis (mainteneur, une seule fois — principe IX)

1. Settings → Code security : activer **Dependabot alerts** et **Dependabot security
   updates** (la recherche de secrets et la protection au push sont déjà actives).
2. **Ne pas** activer le « Default setup » CodeQL, ou le désactiver s'il l'a été : il entre en
   conflit avec le workflow avancé `codeql.yml`.
3. Ruleset `ProtectTheMain` : cible = branche par défaut uniquement.

## 1. Validateur d'exceptions (local)

```bash
python3 -m unittest discover -s tests/security -v
python3 scripts/security/check_exceptions.py        # attendu : code 0, registre vide
```

## 2. Première exécution sur la PR de la feature

Ouvrir la PR `001-security-ci-baseline` → `main`. Attendu : les 6 contrôles de
[contracts/required-checks.md](contracts/required-checks.md) apparaissent et sont verts en
moins de 10 minutes (SC-003).

Vérifier ensuite que **chaque outil a publié ses résultats** (un contrôle vert ne le prouve
pas, LL-003) :

```bash
gh api 'repos/aboigues/bitumap/code-scanning/analyses?per_page=30' \
  --jq '[.[] | .tool.name] | unique'
# attendu : CodeQL, Gitleaks (ou gitleaks), Trivy, zizmor
```

Après fusion, le mainteneur ajoute ces contrôles et la règle *code scanning* au ruleset.

## 3. Branches pièges (SC-001) — jamais fusionnées

Pour chaque cas : créer une branche `trap/<cas>`, ouvrir une PR en brouillon, constater le
blocage, puis **fermer la PR et supprimer la branche**.

| Cas | Contenu de la branche | Contrôle attendu en échec |
|---|---|---|
| `trap/secret` | un fichier contenant un faux jeton au format AWS de la documentation Gitleaks | `security / secrets` (et possiblement la protection au push) |
| `trap/dependency` | un `requirements.txt` déclarant une version publiquement vulnérable (ex. `jinja2==2.10`) | `security / dependency-review`, `security / vulnerabilities-iac` |
| `trap/iac` | un `Dockerfile` avec `USER root` et une image non épinglée | `security / vulnerabilities-iac` |
| `trap/workflow` | un workflow avec `uses: actions/checkout@v4` (non épinglé) et sans `permissions` | `security / workflows-audit` |
| `trap/exception-expired` | une exception dont `expires` est dans le passé | `security / exceptions` |

Pour `trap/secret` : si la protection au push bloque déjà le push, le test est réussi (couche
1). Utiliser un jeton **factice** ; un vrai secret poussé par erreur doit être révoqué et
faire l'objet d'une entrée `LESSON-LEARNED.md`.

## 4. Surveillance continue (US2)

- Actions → `security` → *Run workflow* (`workflow_dispatch`) sur `main` : les résultats
  apparaissent dans Security → Code scanning.
- Vérifier la présence de `.github/dependabot.yml` dans Insights → Dependency graph →
  Dependabot.

## 5. Livraison (US3)

```bash
git tag v0.0.1 && git push origin v0.0.1     # action du mainteneur
```

Attendu : la version `v0.0.1` est créée avec `bitumap-v0.0.1.cdx.json` attaché (SC-005).

## 6. Revue mensuelle (mainteneur)

- Security → Code scanning → alertes ignorées : chacune porte un commentaire `EXC-NNN`
  présent dans `.security/exceptions.toml`.
- Aucune exception n'approche de l'expiration sans décision.
