# Amorçage Scaleway

Socle que l'IaC OpenTofu ne peut pas créer elle-même (constitution, « Contraintes
techniques »). Tout le reste de l'infrastructure est décrit en OpenTofu.

## Ce que crée `bootstrap.sh`

| Ressource | Nom | Détail |
|---|---|---|
| Projet | `BITUMAP` | région `fr-par`, isole ressources, droits et facturation |
| Application IAM | `bitumap-tofu` | utilisée par OpenTofu et la CI |
| Politique IAM | `bitumap-tofu-project` | limitée au projet `BITUMAP` : ContainerRegistry, Containers, ServerlessJobs, ObjectStorage, SecretManager, Observability (FullAccess) |
| Clé API | — | expire à 180 jours ; écrite dans le profil scw local `bitumap`, jamais affichée |
| Bucket d'état | `bitumap-tofu-state-<suffixe>` | privé, versionné, dans le projet `BITUMAP` |

L'application `bitumap-tofu` n'a **aucun** droit IAM : créer d'autres applications ou modifier
les politiques passe par ce script, exécuté par un humain avec le profil d'administration.

## Exécution

```bash
cp .env.example .env          # une fois ; renseigner ADMIN_PROFILE (fichier non versionné)
infra/bootstrap/bootstrap.sh
# ou, sans .env : ADMIN_PROFILE=<profil-admin> infra/bootstrap/bootstrap.sh
```

- `ADMIN_PROFILE` est obligatoire : c'est le profil scw local d'administration. Son nom
  n'est pas versionné (dépôt public) : il vient de `.env` ou de la variable d'environnement,
  qui est prioritaire. `.env` est lu comme des données, jamais exécuté.
- Idempotent : relancer ne recrée rien et ne régénère pas la clé.
- **Avant toute PR modifiant ce script** : l'exécuter deux fois de suite, la seconde doit
  n'afficher que des « déjà présent » (LL-001).
- Le script s'arrête sur la première erreur en affichant la ligne et la commande en cause.

## Ajouter un droit à l'application

Ajouter le jeu de permissions dans `PERMISSION_SETS`, puis mettre à jour la politique
existante (le script ne modifie pas une politique déjà créée) :

```bash
scw -p "$ADMIN_PROFILE" iam policy list policy-name=bitumap-tofu-project
scw -p "$ADMIN_PROFILE" iam rule update policy-id=<id> rules.0.project-ids.0=<projet> \
  rules.0.permission-set-names.0=... # liste complète
```

## Rotation de la clé

Avant expiration (180 jours) : supprimer la clé dans la console IAM, vider `access-key` et
`secret-key` du profil `bitumap` (`scw -p bitumap config unset access-key`, idem
`secret-key`), puis relancer le script.
