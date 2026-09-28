# Contrat : configuration

Variables d'environnement lues par `bitumap.config` (pydantic-settings). Les **secrets** sont
injectés depuis Secret Manager (références de secret du conteneur et du job), jamais dans le
dépôt ni dans `.env`.

## Réglages (valeurs de départ, spec « Assumptions »)

| Variable | Défaut | Rôle |
|---|---|---|
| `BITUMAP_QUOTA_GENERATION_COMPTE_JOUR` | 5 | FR-005 |
| `BITUMAP_QUOTA_GENERATION_GLOBAL_JOUR` | 50 | FR-005 |
| `BITUMAP_QUOTA_LIEN_EMAIL_HEURE` | 3 | FR-005 |
| `BITUMAP_QUOTA_LIEN_ORIGINE_HEURE` | 10 | FR-005 |
| `BITUMAP_LIEN_VALIDITE_MIN` | 15 | FR-006 |
| `BITUMAP_SESSION_JOURS` | 7 | FR-006 |
| `BITUMAP_COMPTE_INACTIF_MOIS` | 12 | FR-027 |
| `BITUMAP_LOT_TAILLE` | 10 | FR-007a |
| `BITUMAP_COMMUNE_DELAI_MAX_MIN` | 30 | FR-017 |
| `BITUMAP_IA_PLAFOND_RAPPORT_EUR` | 2 | FR-024 |
| `BITUMAP_IA_PLAFOND_JOUR_EUR` | 20 | FR-024 |
| `BITUMAP_IA_MODELE` | issu de l'évaluation (R7) | FR-014 |
| `BITUMAP_IA_TARIF_ENTREE_EUR_MTOK`, `…_SORTIE_…` | tarif Scaleway en vigueur | calcul du coût |
| `BITUMAP_PANORAMAX_RAYON_M` | 30 | FR-015 |
| `BITUMAP_BUCKET_RAPPORTS`, `BITUMAP_BUCKET_CACHE` | noms des buckets | |
| `BITUMAP_EMAIL_EXPEDITEUR` | adresse sur le domaine vérifié | FR-028 |
| `BITUMAP_URL_PUBLIQUE` | URL du service | liens des e-mails |

L'intervalle entre lots (15 min) et la durée maximale d'un lot (3 h) sont réglés dans
OpenTofu (planification et `timeout` du job).

## Secrets (Secret Manager)

| Secret | Utilisé par |
|---|---|
| `bitumap-db-url` | API, job |
| `bitumap-altcha-hmac` | API |
| `bitumap-sel-origine` | API (empreinte salée des adresses IP, renouvelée chaque jour) |
| `bitumap-s3` (clé d'accès de l'application d'exécution) | API, job |
| `bitumap-tem` (clé d'envoi d'e-mails) | API, job |
| `bitumap-genai` (clé Generative APIs) | job |

Chaque composant tourne avec **sa propre** application IAM limitée à ce dont il a besoin
(`bitumap-api` : base, lecture des rapports, e-mail ; `bitumap-job` : base, écriture rapports
et cache, e-mail, IA). L'application `bitumap-tofu` n'ayant aucun droit IAM (bootstrap), ces
applications, leurs politiques et leurs clés sont créées par
`infra/bootstrap/bootstrap.sh` (profil d'administration, action humaine) ; les clés sont
écrites directement dans Secret Manager, jamais affichées. Serverless SQL Database
s'authentifie avec ces clés IAM (identifiant = application, mot de passe = clé secrète).
