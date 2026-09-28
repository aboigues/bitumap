# Recherche (Phase 0) : Rapport de risque d'orniérage à la demande

Vérifications faites le 2026-09-28 (API publiques interrogées en direct, registres PyPI et
GitHub, documentation Scaleway).

## R1. État applicatif : comptes, liens, sessions, quotas, file d'attente

- **Décision** : **Scaleway Serverless SQL Database** (PostgreSQL), redescend à zéro vCPU au
  repos ; seule la capacité de stockage (quelques Mo) est facturée en continu.
- **Raison** : la spec impose des opérations concurrentes et transactionnelles : lien de
  connexion à usage unique, preuve antibot à usage unique, compteurs de quotas, file avec
  position, prise en charge exclusive d'une demande par un seul lot (`SELECT … FOR UPDATE
  SKIP LOCKED`), rattachement des demandes concurrentes (contrainte d'unicité). Les faire sur
  des fichiers du stockage objet serait plus fragile et plus complexe.
- **Coût** : démarrage à froid de quelques secondes quand la base est endormie (acceptable :
  SC-001 = 10 s). Compute facturé à l'usage.
- **Alternatives écartées** : fichiers JSON sur le stockage objet avec écritures
  conditionnelles (possibles chez Scaleway, mais quotas et files deviennent du code maison
  risqué) ; Scaleway Queues (SQS) : ne donne ni position dans la file ni état, il faudrait
  quand même une base ; base PostgreSQL managée classique : facturée à l'heure au repos
  (principe II).
- **Constitution** : écart au principe II (stockage facturé au repos) justifié dans le suivi
  de complexité du plan.

## R2. Traitement par lots

- **Décision** : **Serverless Jobs** avec planification intégrée `cron { schedule =
  "*/15 * * * *", timezone = "Europe/Paris" }` (fournisseur Scaleway, ressource
  `scaleway_job_definition`) ; délai maximal d'exécution 3 h (`timeout`).
- Le job démarre, prend jusqu'à 10 demandes en file de façon exclusive, s'arrête aussitôt
  si la file est vide (SC-008 : < 30 s).
- Chevauchement de deux lots : sans risque, la prise en charge est exclusive (R1).

## R3. Adresse e-mail et envoi

- **Décision** : **Scaleway Transactional Email** (France) : offre gratuite de quelques
  centaines d'e-mails, puis environ 1 € les 1 000.
- **Prérequis humain** : un **nom de domaine d'envoi** vérifié (SPF, DKIM, DMARC, MX).
  C'est la seule dépendance externe non encore disponible : voir quickstart §0.
- Contenu minimal (FR-028) : lien, délai, nom de la commune.

## R4. Authentification sans mot de passe

- Lien de connexion : jeton aléatoire de 32 octets ; seule son **empreinte SHA-256** est
  stockée ; usage unique ; 15 min.
- Session : identifiant aléatoire dans un cookie `__Host-session` (`Secure`, `HttpOnly`,
  `SameSite=Lax`, chemin `/`), empreinte stockée en base, 7 jours.
- Formulaires `POST` : jeton anti-CSRF lié à la session en plus de `SameSite`.
- Réponse identique que le compte existe ou non (FR-006b).
- **Alternatives écartées** : jetons signés sans état (impossible de garantir l'usage
  unique) ; fournisseur d'identité externe (tiers, souvent hors UE).

## R5. Antibot

- **Décision** : **ALTCHA** : widget `v3.2.3` (auto-hébergé, servi par l'API, pas de CDN)
  et vérification serveur avec la bibliothèque Python `altcha` 2.1.0 ; clé HMAC dans Secret
  Manager ; défi valable 10 min ; signature d'un défi résolu enregistrée pour refuser toute
  réutilisation.
- **Raison** : sans tiers, sans cookie, RGPD, accessible (WCAG 2.2 AA), licence MIT.

## R6. Sources de données (accès vérifié en direct)

| Donnée | Accès | Portée | Constat |
|---|---|---|---|
| Arrêts | IDFM `arrets` (API Opendatasoft, export) | région, **une fois par lot** | Licence Ouverte 2.0, coordonnées Lambert 93 |
| Offre de bus | IDFM `offre_hebdomadaire_moyenne_hors_vacances` | région, une fois par lot | Licence Ouverte 2.0 ; courses par jour et par tranche horaire, par arrêt et par ligne |
| Lignes | IDFM `referentiel-des-lignes` | région, une fois par lot | **ODbL** |
| Feux, giratoires, revêtement, itinéraires bus | extrait **Geofabrik Île-de-France** (`.osm.pbf`) lu avec `osmium` | région, une fois par lot | ODbL |
| **Type de route et gestionnaire** | Géoplateforme WFS `BDTOPO_V3:troncon_de_route` : `cpx_classement_administratif`, `cpx_gestionnaire`, `cpx_numero`, `importance`, `urbain` | commune | ex. bd G. Clemenceau : `Départementale`, `Hauts-de-Seine`, `D9B` ; les voies communales ont un classement **vide** |
| Bâtiments et hauteurs | WFS `BDTOPO_V3:batiment` | commune | ombres (méthode 1.0) |
| Pentes | API altimétrie IGN (`ign_rge_alti_wld`), points à ±30 m | commune | réponse en ms |
| Arbres | orthophoto infrarouge couleur (Géoplateforme) : indice de végétation | commune | méthode du prototype |
| Îlots de chaleur | Institut Paris Region (open data ArcGIS) | région, cache long | portail joignable |
| Âge de l'enrobé | orthophotos historiques (Géoplateforme, plusieurs millésimes) | points P1 | vignettes envoyées au modèle vision |
| Photos de rue | API Panoramax (STAC, `bbox`) | commune | **licence variable par photo** (CC-BY-SA-4.0 constatée) : relevée photo par photo |
| Code postal → communes | API Géo | requête | `95000` → 4 communes ; **Paris** : `type=arrondissement-municipal` (`75011` → 75111) |

- **Type de route (FR-013)** : valeur BD TOPO si renseignée ; classement vide ⇒ « communale
  (présumée) » ; recoupement avec la référence OSM (`ref=D 9B`…) ; divergence ⇒ « à
  vérifier ». Gestionnaire : `cpx_gestionnaire` ou, par défaut, la commune.
- **Paris** : l'unité est l'**arrondissement** (code 751xx), sinon Paris dépasserait les
  bornes de temps de SC-002.

## R7. Modèle vision (âge de l'enrobé)

- Modèles vision disponibles en serverless sur Scaleway Generative APIs (hébergés en France,
  API compatible OpenAI) : `mistral-medium-3.5-128b`, `mistral-small-3.2-24b-instruct-2506`,
  `qwen3.8-27b`, `qwen3.6-35b-a3b`, `gemma-4-26b-a4b-it`, `pixtral-12b-2409`.
- **Décision** : choisir par **évaluation comparative** sur l'échantillon SC-012 (30 points
  P1 à date de réfection connue) entre `mistral-medium-3.5-128b`, `mistral-small-3.2-24b`
  et `qwen3.8-27b` : on retient le plus exact, puis le moins cher en cas d'égalité ; le
  modèle, la version du prompt et le seuil sont versionnés avec la méthode.
- Sortie contrainte (schéma JSON : période, confiance, justification courte) ; toute réponse
  hors schéma ⇒ « non évalué ».
- Coût calculé à partir des jetons consommés et du tarif configuré ; plafonds FR-024
  appliqués **avant** chaque appel.

### R7-bis. Estimation du coût de l'IA vision (2026-09-28)

Tarifs Scaleway Generative APIs (serverless, € par million de jetons, entrée / sortie) et
taille des jetons d'image (documentation des modèles). Hypothèses : P1 = 20 % des points
(Courbevoie : 31 P1 sur 153) ; par point, 6 orthophotos 512×512 px, environ 600 jetons de
consignes, environ 150 jetons de réponse.

| Modèle | € entrée / sortie | Jetons par image | € / point | € / rapport Courbevoie (31 P1) | € / grande commune (100 P1) |
|---|---|---|---|---|---|
| mistral-medium-3.5-128b | 1,50 / 7,50 | 361 | 0,0053 | 0,16 | 0,53 |
| mistral-small-3.2-24b | 0,15 / 0,35 | 361 | 0,0005 | 0,015 | 0,05 |
| qwen3.8-27b | 0,60 / 3,30 | 256 | 0,0018 | 0,055 | 0,18 |
| pixtral-12b | 0,20 / 0,20 | 1 024 | 0,0014 | 0,043 | 0,14 |
| gemma-4-26b | 0,25 / 0,50 | 64 (896 px max) | 0,0003 | 0,010 | 0,03 |

Scénarios (rapport type Courbevoie) :

| Modèle | 1 rapport/jour (€/mois) | 10 rapports d'un coup (€) | 10 rapports/jour (€/mois) |
|---|---|---|---|
| mistral-medium-3.5 | 4,90 | 1,63 | 49 |
| mistral-small-3.2 | 0,43 | 0,14 | 4,35 |
| qwen3.8-27b | 1,65 | 0,55 | 16,50 |

Conséquences :

- Les plafonds (2 €/rapport, 5 €/jour depuis la revue de la PR #14) ne sont pas approchés en usage normal : ils
  protègent contre les abus et les erreurs (boucle, image trop grande), pas contre l'usage.
- Le **choix du modèle** pèse ×11 (medium vs small) ; le **mode de traitement** (lot ou un par
  un) ne change pas le coût de l'IA : il y a autant de points à analyser.
- Leviers réels : (1) cache par point des réponses IA, indexé par point, millésimes
  d'orthophoto, modèle et version du prompt : une commune régénérée sans nouveau millésime
  ne coûte plus rien en IA ; (2) API de traitement par lots de Scaleway, **-50 %**, mais délai
  de réponse à vérifier face à SC-002 (45 min) ; (3) premier million de jetons offert selon la
  page tarifs (environ 11 rapports Courbevoie avec les Mistral).
- À mesurer à l'implémentation : jetons réels par image (redimensionnement propre à chaque
  modèle), longueur réelle des réponses (les modèles Qwen peuvent raisonner longuement).

## R8. Rapport

- **Décision** : HTML autonome rendu avec Jinja2, **carte en SVG dessinée à partir des
  données** comme dans le prototype (contour communal, voies bus, points), sans fond de
  carte : **entièrement lisible hors connexion** (va au-delà de FR-020).
- **Alternative écartée** : MapLibre GL JS avec fond IGN (bibliothèque de plusieurs
  centaines de Ko, dépendance réseau) : reportée, le README sera aligné.
- Consultation : l'API vérifie la session puis **sert le fichier elle-même** depuis le
  stockage privé (pas de lien signé transmissible).

## R9. Stack et versions (dernières stables au 2026-09-28)

| Paquet | Version | Paquet | Version |
|---|---|---|---|
| Python | 3.14.7 | uv | 0.12.19 (local : 0.9.18, à mettre à jour) |
| FastAPI | 0.141.1 | uvicorn | 0.54.0 |
| pydantic | 2.13.5 | pydantic-settings | 2.15.0 |
| geopandas | 1.1.4 | shapely | 2.1.2 |
| pyproj | 3.8.0 | rasterio | 1.5.1 |
| numpy | 2.5.3 | pvlib | 0.16.1 |
| osmium | 4.3.1 | pyarrow | 25.0.1 |
| jinja2 | 3.1.6 | httpx | 0.28.1 |
| psycopg | 3.3.6 | psycopg-pool | 3.3.3 |
| boto3 | 1.43.103 | openai | 3.19.2 |
| altcha (Python) | 2.1.0 | altcha (widget) | 3.2.3 |
| pillow | 12.3.0 | pytest | 9.1.1 |
| ruff | 0.16.9 | respx / moto | 0.23.1 / 5.2.3 |
| OpenTofu | 1.12.6 | fournisseur Scaleway | 2.83.1 |

Figées dans `pyproject.toml` / `uv.lock` et `infra/tofu/versions.tf`.

## R9-bis. Image de base des conteneurs (décision du 2026-09-28)

- **Constat** : avec `python:3.14-slim` (Debian 13), Trivy relevait 46 vulnérabilités élevées ou
  critiques : 2 corrigeables (`msgpack` et `setuptools`, embarqués dans `pip`) et **44 sans
  aucun correctif Debian** (`util-linux`, `ncurses`, `systemd`, `perl-base`…), qui auraient
  bloqué toutes les PR indéfiniment.
- **Décision (mainteneur)** : image de base **minimale** Chainguard (Wolfi) :
  `cgr.dev/chainguard/python:latest-dev` pour construire, `cgr.dev/chainguard/python:latest`
  pour exécuter (Python 3.14.7), **épinglées par digest**, construction en deux étapes. Image
  d'exécution sans shell ni gestionnaire de paquets, non root (65532), code propriété de root
  (lecture seule pour l'application).
- **Résultat mesuré** : **0 vulnérabilité, toutes gravités**, sur `api` et `job` ; 1,1 Go
  (dépendances géospatiales : GDAL 3.12, PROJ, SciPy, pandas) ; bibliothèques natives vérifiées.
- **Alternatives écartées** : bloquer seulement le corrigeable (`--ignore-unfixed`) ; une
  exception par vulnérabilité (44 entrées renouvelées tous les 90 jours).
- **Points d'attention** : l'offre gratuite de Chainguard ne publie que les étiquettes `latest` :
  le digest épinglé est mis à jour par Dependabot (écosystème `docker`, répertoire `/docker`) ;
  fournisseur d'images américain, utilisé seulement à la construction (aucune donnée transmise,
  principe III non concerné).

## R10. Infrastructure et déploiement

- OpenTofu, backend S3 sur le bucket d'état, **verrouillage natif** `use_lockfile = true`
  (écritures conditionnelles gérées par le stockage objet Scaleway), **chiffrement de l'état**
  (bloc `encryption`, clé dérivée d'une phrase secrète hors dépôt).
- Images : construites et analysées en CI (Trivy, non root, épinglées), poussées vers le
  Container Registry Scaleway **à la livraison** (tag) par une application IAM dédiée
  `bitumap-ci` limitée à l'écriture du registre ; comme les applications d'exécution
  `bitumap-api` et `bitumap-job`, elle est créée par le **bootstrap** (l'application OpenTofu
  n'a aucun droit IAM) ; déploiement par
  `tofu apply` lancé par le mainteneur (principe IX : la mise en production reste humaine).
- CI : `python` ajouté à CodeQL, nouveau contrôle requis `tests` (ruff + pytest),
  Dependabot `uv`, `docker` et `opentofu`.
