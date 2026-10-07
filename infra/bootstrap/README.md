# Amorçage Scaleway

Socle que l'IaC OpenTofu ne peut pas créer elle-même (constitution, « Contraintes
techniques »). Tout le reste de l'infrastructure est décrit en OpenTofu.

## Ce que crée `bootstrap.sh`

| Ressource | Nom | Détail |
|---|---|---|
| Projet | `BITUMAP` | région `fr-par`, isole ressources, droits et facturation |
| Application IAM | `bitumap-tofu` | utilisée par OpenTofu et la CI |
| Politique IAM | `bitumap-tofu-project` | limitée au projet `BITUMAP` : ContainerRegistry, Containers, ServerlessJobs, ObjectStorage, SecretManager, Observability, ServerlessSQLDatabase, TransactionalEmail (FullAccess) |
| Clé API | — | expire à 180 jours ; écrite dans le profil scw local `bitumap`, jamais affichée |
| Bucket d'état | `bitumap-tofu-state-<suffixe>` | privé, versionné, dans le projet `BITUMAP` |
| Application IAM | `bitumap-api` | API : données de la base (pas la structure), objets, envoi d'e-mails ; clé → Secret Manager |
| Application IAM | `bitumap-job` | job : base (migrations comprises), objets, envoi d'e-mails, modèles d'IA ; clé → Secret Manager |
| Application IAM | `bitumap-ci` | CI : publication des images dans le registre ; clé → secrets GitHub du dépôt |
| Secrets | `bitumap-cle-api`, `bitumap-cle-job` | clé secrète IAM seule (injectée telle quelle dans le conteneur et le job) |
| Secrets | `bitumap-id-api`, `bitumap-id-job` | identifiants publics `{application_id, access_key}`, lus par OpenTofu |
| Secrets GitHub | `BITUMAP_CI_CLE_ACCES`, `BITUMAP_CI_CLE_SECRETE` | clé de `bitumap-ci` |
| Offre Transactional Email | `essential` | gratuite, 300 e-mails par mois pour l'organisation ; sans elle, le domaine d'envoi est refusé (403). Le fournisseur OpenTofu ne sait que la lire (LL-024) |

Chaque application a sa politique `<nom>-project`, limitée au projet `BITUMAP` ; les jeux
de permissions sont listés en tête du script. La restriction **par bucket** (l'API ne
peut pas écrire les rapports, le job ne voit pas les photos) est faite par les politiques
de bucket d'OpenTofu (`infra/tofu/stockage.tf`). Aucune clé n'est affichée : elles passent
par un fichier temporaire en mode 600 (Secret Manager) ou par l'entrée standard de `gh`
(secrets GitHub), et ne sont jamais régénérées si elles existent déjà.

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
- Prérequis : `scw`, `jq`, et `gh` connecté avec les droits d'administration du dépôt
  (secrets GitHub de la CI).
- Idempotent : relancer ne recrée rien et ne régénère aucune clé ; les règles des
  politiques sont remises à la liste du script.
- **Avant toute PR modifiant ce script** : l'exécuter deux fois de suite, la seconde doit
  n'afficher que des « déjà présent » (LL-001).
- Le script s'arrête sur la première erreur en affichant la ligne et la commande en cause.

## Ajouter un droit à une application

Ajouter le jeu de permissions dans la liste correspondante du script (`PERMISSION_SETS`,
`API_PERMISSION_SETS`, `JOB_PERMISSION_SETS`, `CI_PERMISSION_SETS`) et relancer le script :
les règles de la politique existante sont remplacées par la liste.

## Démantèlement

`demantelement.sh` défait, dans l'ordre inverse, tout ce que crée `bootstrap.sh` : secrets
GitHub de la CI, secrets `bitumap-cle-…` et `bitumap-id-…`, applications et politiques
(leurs clés sont révoquées avec elles), bucket d'état vidé de toutes ses versions, clé du
profil `bitumap`, fichier d'identifiants du backend, puis le projet. À lancer **après**
`tofu destroy` (procédure complète : [`infra/tofu/README.md`](../tofu/README.md),
« Destruction ») : il s'arrête si une ressource gérée par OpenTofu existe encore.

```bash
infra/bootstrap/demantelement.sh --simulation   # affiche les actions, ne supprime rien
infra/bootstrap/demantelement.sh                # demande de taper « DÉTRUIRE BITUMAP »
```

Idempotent : relancé après une interruption, il ignore ce qui n'existe plus. Prérequis en
plus de ceux du bootstrap : `uv` et l'environnement Python du dépôt (vidage du bucket
versionné, que `scw` ne sait pas faire).

## Rotation des clés

Clés d'exécution et de CI (365 jours) : avant expiration, désactiver la version du secret
(`bitumap-cle-<composant>`) ou supprimer les secrets GitHub `BITUMAP_CI_CLE_…`, supprimer
l'ancienne clé dans la console IAM, relancer le script, puis `tofu apply` (nouvelle clé
injectée dans le conteneur et le job).

Après une rotation de la clé de `bitumap-tofu`, relancer `infra/tofu/identifiants-etat.sh`.

Clé de `bitumap-tofu` (180 jours) : avant expiration, supprimer la clé dans la console IAM, vider `access-key` et
`secret-key` du profil `bitumap` (`scw -p bitumap config unset access-key`, idem
`secret-key`), puis relancer le script.
