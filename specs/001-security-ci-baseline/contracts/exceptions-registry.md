# Contrat : registre des exceptions `.security/exceptions.toml`

## Format

```toml
# Registre des exceptions de sécurité (principe I, FR-015).
# Durée maximale : 90 jours. Une exception expirée fait échouer `security / exceptions`.

[[exception]]
id = "EXC-001"
tool = "trivy"                 # trivy | gitleaks | codeql | dependency-review
finding = "CVE-2026-12345"     # CVE, GHSA, empreinte Gitleaks ou n° d'alerte CodeQL
reason = "Faux positif : fonction vulnérable non appelée ; atténuation : …"
owner = "aboigues"
created = 2026-10-01
expires = 2026-12-30
```

Fichier vide (aucune `[[exception]]`) = valide.

## Correspondance avec les fichiers des outils

| Outil | Fichier | Entrée attendue |
|---|---|---|
| Trivy | `.trivyignore` | `CVE-2026-12345 exp:2026-12-30` (même date que `expires`) |
| Gitleaks | `.gitleaksignore` | empreinte `commit:fichier:règle:ligne` = `finding` |
| CodeQL | interface GitHub | alerte ignorée avec commentaire `EXC-NNN` |
| dependency-review | `.github/workflows/security.yml` (`allow-ghsas`) | GHSA = `finding` |

## Interface du validateur

```text
python3 scripts/security/check_exceptions.py [--registry PATH] [--root PATH] [--today YYYY-MM-DD]
```

- Code retour `0` : registre valide.
- Code retour `1` : au moins une erreur ; une ligne par erreur sur la sortie d'erreur, forme
  `ERREUR <id|fichier>: <message>`.
- Code retour `2` : fichier illisible ou TOML invalide.
- `--today` sert aux tests (date injectée, résultats reproductibles).

Erreurs détectées : champ manquant ou vide, `tool` inconnu, `id` dupliqué, dates invalides,
`expires ≤ today` (expirée), `expires − created > 90 j`, entrée `.trivyignore` /
`.gitleaksignore` sans exception active correspondante, date `exp:` différente de `expires`.
