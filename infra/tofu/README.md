# Infrastructure OpenTofu

Toutes les ressources Scaleway de bitumap hors socle (le socle est créé par
[`infra/bootstrap/`](../bootstrap/README.md)). Projet `BITUMAP`, région `fr-par`.
Spécification : `specs/002-on-demand-report/tasks.md`, phase 7.

| Fichier | Contenu |
|---|---|
| `versions.tf` | OpenTofu 1.13.1, fournisseurs Scaleway 2.84.0 et random 3.9.1 ; chiffrement de l'état et des plans |
| `backend.tf` | état dans le bucket du bootstrap, verrou par fichier (`use_lockfile`) ; identifiants lus dans `~/.config/bitumap/etat-tofu` |
| `identifiants-etat.sh` | contrôle `terraform.tfvars` (bucket d'état du projet), puis écrit ce fichier (mode 600) depuis le profil scw `bitumap`, sans rien afficher |
| `variables.tf` | bucket d'état, phrase de chiffrement, application `bitumap-tofu`, domaine du service, autorisation de destruction |
| `identites.tf` | identifiants publics des applications `bitumap-api` et `bitumap-job` (lus dans Secret Manager) |
| `stockage.tf` | buckets rapports, cache et photos des relevés, cycles de vie, CORS, politiques de bucket |
| `base.tf` | base Serverless SQL (0 vCPU au repos) |
| `registre.tf` | registre privé des images |
| `secrets.tf` | secrets générés : clé HMAC ALTCHA, sel des adresses IP |
| `api.tf` | conteneur de l'API (0 à 2 instances, image par digest, sonde `/health`), domaine du service |
| `job.tf` | job de lot (toutes les 15 min, 3 h au plus), URL de sa base dans Secret Manager |
| `courriel.tf` | domaine d'envoi des e-mails (Transactional Email) |
| `sorties.tf` | buckets, base, registre, adresses du conteneur et du job, enregistrements DNS à créer |

L'alerte de budget n'est pas gérée par OpenTofu : voir « Alerte de budget » ci-dessous.

## Coût estimé

Tarifs publiés par Scaleway, hors TVA, relevés le 2026-10-05. Au repos, le total est
d'environ **0,60 à 1 € par mois**, sous le plafond de 5 €/mois (FR-029).

| Ressource | Tarif | Usage prévu | €/mois |
|---|---|---|---|
| Buckets (Standard Multi-AZ) | 0,016 €/Go/mois ; requêtes et 75 Go de sortie par mois inclus | 5 à 30 Go (cache des sources expiré à 30 j, photos plafonnées à 20 Go) | 0,08 à 0,50 |
| Base Serverless SQL, stockage | 0,000272 €/Go/h (≈ 0,20 €/Go/mois), facturé même au repos | < 0,2 Go | < 0,05 |
| Base Serverless SQL, calcul | 0,13752 €/vCPU/h, **rien au repos** ; active jusqu'à 5 min après la dernière requête | réveillée par l'usage réel seulement (voir ci-dessous) | ≈ 0 à quelques € |
| Registre privé | 0,027 €/Go/mois | 2 images, peu de versions gardées | ≈ 0,08 |
| Secret Manager | 0,04 € par version de secret et par mois ; 0,03 € les 10 000 appels | 8 à 10 secrets | ≈ 0,40 |
| Conteneur de l'API, job | 1 € les 100 000 vCPU-s ; 0,20 € les 100 000 Go-s ; 200 000 vCPU-s et 400 000 Go-s gratuits par mois | usage faible | 0 à 1 |
| Transactional Email | 300 e-mails gratuits par mois pour l'organisation, puis 0,25 € les 1 000 | quelques dizaines | 0 |

**Réveils de la base** : chaque requête réveille la base pour au moins 5 minutes facturées.
Un job lancé toutes les 15 minutes qui interrogerait la base coûterait 16 à 33 €/mois à vide.
Décision (2026-10-05) : le job ne se connecte à la base que si un **témoin de demande** est
présent dans le bucket du cache (`file/<demande>`, déposé par l'API à la mise en file ; seul
droit de l'API sur ce bucket), plus un passage quotidien pour la purge et un passage après
chaque nouvelle migration (T096, `specs/002-on-demand-report/contracts/lot-job.md`).

Sources : [Serverless](https://www.scaleway.com/en/pricing/serverless/),
[Object Storage](https://www.scaleway.com/en/pricing/storage/),
[Serverless SQL Database](https://www.scaleway.com/en/pricing/managed-databases/),
[Container Registry](https://www.scaleway.com/en/pricing/containers/),
[Secret Manager](https://www.scaleway.com/en/pricing/security-and-account/),
[Transactional Email](https://www.scaleway.com/en/pricing/managed-services/),
[mise en veille de la base](https://www.scaleway.com/en/docs/serverless-sql-databases/concepts/).

## Mise en œuvre (action humaine, principe IX)

Aucun agent n'exécute `tofu apply`. Prérequis : OpenTofu 1.13.1, profil scw `bitumap`, le
bootstrap exécuté (il crée les secrets `bitumap-id-…` lus par `identites.tf`).

```bash
cd infra/tofu
tofu version                                   # 1.13.1 (versions.tf refuse une autre version)
cp terraform.tfvars.example terraform.tfvars   # valeurs de la sortie du bootstrap, domaine
./identifiants-etat.sh                         # contrôle terraform.tfvars, identifiants du backend
read -rs TF_VAR_phrase_chiffrement && export TF_VAR_phrase_chiffrement   # ≥ 32 caractères
tofu init -input=false   # jamais d'invite : une variable manquante est une erreur
tofu plan -input=false -out=bitumap.tfplan
tofu apply bitumap.tfplan
```

### Déploiement des services (conteneur, job, e-mails)

Deux domaines distincts, tous deux sous-domaines d'un domaine du mainteneur : le service
(`domaine_service`, un CNAME vers le conteneur) et l'envoi d'e-mails (`domaine_envoi`, par
exemple `courriel.<domaine_service>`). Un CNAME ne peut cohabiter avec aucun autre
enregistrement : SPF et MX ne peuvent donc pas être posés sur le domaine du service.

1. Dans `terraform.tfvars` : `domaine_envoi`, `digest_api` et `digest_job` (notes de la
   version : `gh release view v<x.y.z>`, lignes « api » et « job »), `email_mainteneur`
   (facultatif). Laisser `activer_domaine` à `false`.
2. `tofu plan -input=false -out=bitumap.tfplan` puis `tofu apply bitumap.tfplan` : crée le
   conteneur, le job, le domaine d'envoi. Le job tourne dès lors toutes les 15 minutes.
3. Chez le registraire, créer les enregistrements donnés par :

   ```bash
   tofu output dns_service    # CNAME du service vers le conteneur
   tofu output dns_courriel   # SPF, DKIM, MX, DMARC du domaine d'envoi
   ```

   Le domaine parent peut avoir sa propre politique DMARC (`sp=`) : l'enregistrement
   `_dmarc` du domaine d'envoi la remplace pour celui-ci.
4. Une fois le CNAME visible (`dig +short CNAME <domaine_service>`), passer
   `activer_domaine = true` dans `terraform.tfvars`, refaire le plan et l'appliquer : Scaleway
   rattache le domaine au conteneur et obtient son certificat.
5. Premier lancement du job, qui crée le schéma de la base :

   ```bash
   scw -p bitumap jobs definition start "$(tofu output -raw job_lot)" args.0=--complet --wait
   ```

   Sans cela, le premier passage planifié le fait aussi (motif `schema`,
   `specs/002-on-demand-report/contracts/lot-job.md`).
6. Vérifier : `curl -sS https://<domaine_service>/health`, puis `tofu refresh` et
   `tofu output courriel_statut` (`checked` une fois les enregistrements vus par
   Scaleway), et quickstart §6.

Nouvelle version : remplacer les digests dans `terraform.tfvars`, refaire le plan, l'appliquer.

### Alerte de budget (T092)

Les budgets Scaleway portent sur **toute l'organisation**, pas sur un projet, et
`bitumap-tofu` n'a aucun droit de facturation : l'alerte est posée à la main.
Console : menu de l'organisation → *Billing* → onglet *Consumption* → *Billing alerts* →
*Create a billing alert* : budget mensuel de 5 €, seuils à 50 % et 100 %, notification par
e-mail. Si l'organisation porte d'autres projets, ajouter leur coût habituel au budget ;
le coût du seul projet BITUMAP se lit dans *Consumption*, filtré par projet. Le coût de
l'IA a en plus sa propre alerte, envoyée par l'application (`BITUMAP_ALERTE_MENSUELLE_EUR`).
[Documentation](https://www.scaleway.com/en/docs/billing/how-to/use-billing-alerts/).

Pièges (LL-021) :

- **Toujours `-input=false`** : OpenTofu configure le backend *avant* de valider les
  variables. Sans `terraform.tfvars`, `tofu init` demande `var.bucket_etat` et accepte
  n'importe quelle réponse (« yes » a désigné le bucket public d'un tiers). Les validations
  de `variables.tf` n'agissent qu'au `plan`.
- **`application_tofu`** est l'identifiant de l'**application IAM** `bitumap-tofu`, pas
  celui du projet : sortie `application_id` du bootstrap, ou console *Organisation → IAM →
  Applications*. C'est le seul principal autorisé à administrer les buckets : un identifiant
  faux enfermerait OpenTofu hors des buckets dès l'apply.
- **Un plan enregistré fige les variables** : après toute modification de
  `terraform.tfvars`, refaire `tofu plan -out=…` avant `tofu apply`.

- Aucune variable d'environnement `AWS_…` ni `SCW_…` : le fournisseur Scaleway lit le
  profil `bitumap` (`provider "scaleway" { profile = "bitumap" }`), le backend lit le
  fichier écrit par `identifiants-etat.sh`. OpenTofu refuse une clé passée en variable
  dans le bloc `backend`, qu'il recopierait dans `.terraform/`. Le format du fichier
  (`aws_access_key_id`, `aws_secret_access_key`) est imposé par le protocole S3 du backend.

- La phrase de chiffrement est choisie par le mainteneur (ex. `openssl rand -base64 48`) ;
  elle n'est écrite nulle part dans le dépôt ni dans `terraform.tfvars`. **Sans elle, l'état
  est illisible** : la garder dans un gestionnaire de mots de passe. Variante : un fichier
  hors dépôt en mode 600 (`export TF_VAR_phrase_chiffrement=…`, chargé par `source`) ; il
  est alors lisible par tout programme lancé sous le compte du poste, agents compris.
- Le domaine du service n'est pas versionné : il est dans `terraform.tfvars`.
- Les politiques de bucket ne laissent l'accès qu'aux applications listées : la console
  Scaleway ne montre plus le contenu des buckets ; passer par `scw -p bitumap` (application
  `bitumap-tofu`).

## Destruction

Supprime **toutes** les données (rapports, cache, photos des relevés, base et ses
sauvegardes, images, secrets) : irréversible. Action humaine.

1. Si des données doivent être gardées, les exporter avant : base
   (`scw -p bitumap sdb-sql backup list`, puis `… backup export`), photos et rapports
   (copie des buckets).
2. Autoriser la suppression des buckets non vides, sans rien détruire encore (seul
   `force_destroy` change), puis détruire :

   ```bash
   cd infra/tofu
   tofu apply -var autoriser_destruction=true      # vérifier : 3 buckets modifiés, rien d'autre
   tofu destroy -var autoriser_destruction=true
   ```

3. Démanteler le socle du bootstrap (applications IAM, clés, secrets écrits par le
   bootstrap, secrets GitHub de la CI, bucket d'état, projet) :

   ```bash
   infra/bootstrap/demantelement.sh --simulation   # liste ce qui sera supprimé
   infra/bootstrap/demantelement.sh                # demande « DÉTRUIRE BITUMAP »
   ```

   Le script refuse de démarrer tant qu'une ressource gérée par OpenTofu existe encore.
   Les enregistrements DNS créés à la main chez le registraire du domaine sont à retirer
   à la main.

## Vérifications avant une PR

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/infra/tofu:/w" -w /w \
  ghcr.io/opentofu/opentofu:1.13.1 fmt -check
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/infra/tofu:/w" -w /w \
  ghcr.io/opentofu/opentofu:1.13.1 init -backend=false
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e TF_VAR_phrase_chiffrement=0123456789abcdef0123456789abcdef \
  -v "$PWD/infra/tofu:/w" -w /w ghcr.io/opentofu/opentofu:1.13.1 validate
```

Trivy (contrôle `vulnerabilities-iac`) analyse aussi ces fichiers.
