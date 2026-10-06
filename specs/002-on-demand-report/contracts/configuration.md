# Contrat : configuration

Variables d'environnement lues par `bitumap.config` (pydantic-settings). Les **secrets** sont
injectés depuis Secret Manager (références de secret du conteneur et du job), jamais dans le
dépôt ni dans `.env`.

**Nommage sur Scaleway** : aucune variable d'environnement ni aucun secret déclaré sur
Scaleway (conteneur, job, Secret Manager) ne peut commencer par `SCW` : ce préfixe est réservé
à Scaleway. Les variables de l'application commencent par `BITUMAP_`, les secrets par
`bitumap-`. (`SCW_PROFILE` de `.env.example` est une variable locale de la CLI `scw`, jamais
déclarée sur Scaleway.)

## Réglages (valeurs de départ, spec « Assumptions »)

| Variable | Défaut | Rôle |
|---|---|---|
| `BITUMAP_QUOTA_GENERATION_COMPTE_JOUR` | 5 | FR-005 |
| `BITUMAP_QUOTA_GENERATION_GLOBAL_JOUR` | 50 | FR-005 |
| `BITUMAP_QUOTA_LIEN_EMAIL_HEURE` | 3 | FR-005 |
| `BITUMAP_QUOTA_LIEN_ORIGINE_HEURE` | 10 | FR-005 |
| `BITUMAP_QUOTA_DEFI_ORIGINE_HEURE` | 60 | défis ALTCHA par heure et par origine |
| `BITUMAP_ALTCHA_ALGORITHME`, `BITUMAP_ALTCHA_COUT` | `PBKDF2/SHA-256`, 5000 | preuve de travail (R5) |
| `BITUMAP_ALTCHA_VALIDITE_MIN` | 10 | durée de validité d'un défi |
| `BITUMAP_ORIGINE_VIA_PROXY` | `false` ; **`true` en production** | origine = dernière adresse de `X-Forwarded-For` (ajoutée par le proxy Scaleway) |
| `BITUMAP_LIEN_VALIDITE_MIN` | 15 | FR-006 |
| `BITUMAP_SESSION_JOURS` | 7 | FR-006 |
| `BITUMAP_COMPTE_INACTIF_MOIS` | 12 | FR-027 |
| `BITUMAP_LOT_TAILLE` | 10 | FR-007a |
| `BITUMAP_COMMUNE_DELAI_MAX_MIN` | 30 | FR-017 |
| `BITUMAP_LOT_HEURE_QUOTIDIENNE_UTC` | 2 | heure UTC du passage quotidien du job sans demande (purge, lots interrompus ; T096) |
| `BITUMAP_IA_PLAFOND_RAPPORT_EUR` | 2 | FR-024 |
| `BITUMAP_IA_PLAFOND_JOUR_EUR` | 5 | FR-024 |
| `BITUMAP_IA_MODELE` | issu de l'évaluation (R7) | FR-014 |
| `BITUMAP_ALERTE_MENSUELLE_EUR` | 5 | FR-029 : seuil d'alerte, sans blocage |
| `BITUMAP_CACHE_RAPPORT_JOURS` | 30 | FR-008 : validité d'un rapport en cache |
| `BITUMAP_EMAIL_MAINTENEUR` | **aucun dans le dépôt** : à renseigner dans les variables GitHub (Actions) ou les variables d'environnement Scaleway (conteneur et job, passées par OpenTofu) ; valeur **fournie ultérieurement** par le mainteneur | destinataire des alertes ; compte mainteneur (modération des relevés, 003). Tant qu'elle est absente : alertes seulement journalisées (avertissement), aucun compte n'a le rôle de mainteneur (photos visibles par leur seul auteur) |
| `BITUMAP_BUCKET_TERRAIN` | `bitumap-terrain` | photos des relevés terrain (003), privé et versionné |
| `BITUMAP_QUOTA_RELEVES_COMPTE_JOUR`, `BITUMAP_QUOTA_PHOTOS_COMPTE_JOUR` | 200, 1 000 | 003 FR-018 |
| `BITUMAP_PHOTOS_PAR_RELEVE`, `BITUMAP_PHOTO_MAX_OCTETS` | 5, 10 Mo | 003 FR-003 |
| `BITUMAP_PHOTO_FORMULAIRE_VALIDITE_S` | 300 | formulaire d'envoi présigné (003 R4) |
| `BITUMAP_PHOTOS_MAX_GO` | 20 | plafond global du stockage des photos (003 R8) |
| `BITUMAP_IA_TARIF_ENTREE_EUR_MTOK`, `…_SORTIE_…` | tarif Scaleway en vigueur | calcul du coût |
| `BITUMAP_PANORAMAX_RAYON_M` | 30 | FR-015 |
| `BITUMAP_BUCKET_RAPPORTS`, `BITUMAP_BUCKET_CACHE` | noms des buckets | |
| `BITUMAP_EMAIL_EXPEDITEUR` | adresse sur le domaine vérifié | FR-028 |
| `BITUMAP_URL_PUBLIQUE` | URL du service | liens des e-mails |
| `BITUMAP_METHODE` | `1.2` | méthode des nouveaux rapports (`1.2` ou `2.0`, toute autre valeur refusée) ; passe à `2.0` à la mise en service de 004, décidée par le mainteneur |
| `BITUMAP_ETE_REFERENCE` | dernier été complet (à partir d'octobre) | été des indicateurs annuels de 004 (FR-007) ; entre dans l'empreinte en 2.0 |
| `BITUMAP_STATION_METEO` | `75114001` (Paris-Montsouris) | station des données quotidiennes (004 R4, partagée avec 007) |
| `BITUMAP_CONTACT_SECURITE` | avis de sécurité privés GitHub du dépôt | `Contact` de `/.well-known/security.txt` |

**Aucune valeur secrète par défaut** (revue de la PR #14) : `BITUMAP_DB_URL`,
`BITUMAP_ALTCHA_HMAC` et `BITUMAP_SEL_ORIGINE` sont obligatoires. En local, ils viennent de
`.env` (non versionné, lu par l'application et par `docker compose`) ; en CI, de secrets
GitHub ; en production, de Secret Manager.

L'intervalle entre lots (15 min) et la durée maximale d'un lot (3 h) sont réglés dans
OpenTofu (planification et `timeout` du job).

## Secrets (Secret Manager)

| Secret | Créé par | Utilisé par |
|---|---|---|
| `bitumap-cle-api`, `bitumap-cle-job` | bootstrap | clé secrète IAM du composant : base (mot de passe), stockage objet, envoi d'e-mails, IA (job) |
| `bitumap-id-api`, `bitumap-id-job` | bootstrap | identifiants publics `{application_id, access_key}`, lus par OpenTofu |
| `bitumap-altcha-hmac` | OpenTofu (`secrets.tf`, aléatoire) | API |
| `bitumap-sel-origine` | OpenTofu (`secrets.tf`, aléatoire) | API (empreinte salée des adresses IP, renouvelée chaque jour) |
| URL de la base de chaque composant | OpenTofu, avec le conteneur et le job | API, job (`BITUMAP_DB_URL` : application et clé du composant, point d'accès de la base) |

Chaque composant tourne avec **sa propre** application IAM limitée à ce dont il a besoin
(`bitumap-api` : données de la base, lecture des rapports, photos, e-mail ; `bitumap-job` :
base et migrations, rapports et cache, e-mail, IA). Une seule clé IAM par composant sert à
la base, au stockage objet, à l'envoi d'e-mails et à l'IA : `BITUMAP_S3_CLE_SECRETE`,
`BITUMAP_TEM_CLE` et `BITUMAP_GENAI_CLE` reçoivent `bitumap-cle-<composant>`. L'application
`bitumap-tofu` n'ayant aucun droit IAM (bootstrap), ces applications, leurs politiques et
leurs clés sont créées par `infra/bootstrap/bootstrap.sh` (profil d'administration, action
humaine) ; les clés sont écrites directement dans Secret Manager, jamais affichées. La
restriction par bucket est faite par les politiques de bucket (`infra/tofu/stockage.tf`).
Serverless SQL Database s'authentifie avec ces clés IAM (identifiant = application, mot de
passe = clé secrète).

Les noms de bucket portent un suffixe aléatoire (unicité sur tout Scaleway) : les variables
`BITUMAP_BUCKET_…` reçoivent les sorties `buckets` d'OpenTofu.

## GitHub (publication des images, T083)

| Nom | Type | Origine | Utilisé par |
|---|---|---|---|
| `BITUMAP_REGISTRE` | variable du dépôt | sortie `registre` d'OpenTofu (`rg.fr-par.scw.cloud/<espace>`) | `release.yml` |
| `BITUMAP_CI_CLE_SECRETE` | secret du dépôt | bootstrap (application `bitumap-ci`) | `release.yml` (`docker login`) |
| `BITUMAP_CI_CLE_ACCES` | secret du dépôt | bootstrap | non utilisé par `release.yml` : `docker login` ne demande que la clé secrète (identifiant `nologin`) |
