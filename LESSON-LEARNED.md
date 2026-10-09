# Retours d'expérience (LESSON-LEARNED)

Fichier imposé par le principe VIII de la constitution (`.specify/memory/constitution.md`).
Il est lu au début de chaque session de travail, humaine ou IA (chargé via `CLAUDE.md`).

## Règles

- Une entrée par incident, bug ou problème rencontré, ajoutée au plus tard dans la PR qui le
  corrige.
- Les entrées les plus récentes sont en haut.
- Une leçon est **ouverte** tant que sa mesure préventive (test, contrôle CI, règle,
  amendement) n'existe pas.
- Aucun secret ni détail exploitable : un incident de sécurité renvoie vers un avis de
  sécurité privé.
- Une leçon qui se répète ou touche un principe déclenche une proposition d'amendement de la
  constitution.

## Modèle d'entrée

```markdown
### LL-NNN — Titre court (AAAA-MM-JJ) — Ouverte | Close

- **Contexte** : où et quand (développement, CI, production, méthode de score).
- **Symptôme** : ce qui a été observé, message d'erreur exact si court.
- **Causes racines** :
  1. Pourquoi ? …
  2. Pourquoi ? …
  3. Pourquoi ? … (jusqu'à la cause sur laquelle on peut agir)
- **Correctif** : ce qui a été changé.
- **Mesure préventive** : test, contrôle CI, règle ou amendement qui empêche la récidive.
- **Références** : commit, PR, issue.
```

## Entrées

### LL-034 — Erreur passagère à la première page après une inactivité (2026-10-09) — Ouverte

- **Contexte** : production v0.1.2, essai du mainteneur juste après le déploiement ; page
  d'un rapport de Paris 17e.
- **Symptôme** : page « Une erreur est survenue. Réessayez plus tard. » (erreur 500) ; la
  même page s'ouvre au rechargement. Le rapport stocké est sain (ouvert en local sans
  erreur).
- **Causes racines** (mécanisme reproduit en local ; trace de production non lue, faute
  d'accès au journal) :
  1. Pourquoi ? La requête a reçu du pool une connexion déjà coupée par la base
     (`AdminShutdown: terminating connection…` en local) ; le pool l'a ensuite jetée, d'où
     le rechargement réussi.
  2. Pourquoi coupée ? La base Serverless SQL se met en veille après 5 min sans requête et
     ferme ses connexions ; le pool gardait les connexions inutilisées 10 min (valeur par
     défaut de psycopg_pool).
  3. Pourquoi donnée telle quelle ? Le pool ne vérifiait pas une connexion avant de la
     donner.
  4. Pourquoi non vu ? En local et en CI, la base PostgreSQL ne se met jamais en veille ; et
     une erreur 500 n'alerte personne (trace dans le journal du conteneur seulement).
- **Correctif** : connexion vérifiée avant d'être donnée (`check=ConnectionPool.check_connection`),
  remplacée si elle est coupée ; connexions inutilisées fermées après 2 min (`max_idle`, au
  plus 4 min d'inactivité). Vaut pour l'API et le job (même pool).
- **Mesure préventive** : tests `test_connexion_coupee_par_la_base_remplacee` (connexion
  coupée côté serveur puis réutilisée ; échoue sans le correctif) et
  `test_connexions_inutilisees_fermees_avant_la_veille`. Reste ouverte jusqu'à la lecture
  de la trace de production ou l'absence de récidive avec v0.1.3. Proposé, non décidé :
  alerte au mainteneur sur les erreurs 500 ; accès au journal en lecture pour le diagnostic.
- **Références** : branche `fix/pool-connexions-veille`.

### LL-033 — Contrôle requis « exceptions » en échec : test avec pytest (2026-10-09) — Close

- **Contexte** : CI de la PR #54, ajout d'un test de structure du workflow `release`.
- **Symptôme** : job `exceptions` en échec : `ModuleNotFoundError: No module named
  'pytest'` à l'import de `tests/security/test_release_attestations.py`.
- **Causes racines** :
  1. Pourquoi ? Le test importait pytest et PyYAML, alors que le job `exceptions` lance
     `tests/security` par `python3 -m unittest`, sans installer les dépendances.
  2. Pourquoi placé là ? Rangé par thème (sécurité), sans lire comment ce dossier est lancé ;
     la règle n'était écrite que dans le docstring de `test_check_exceptions.py`.
  3. Pourquoi non vu en local ? Le test a été lancé avec `uv run pytest`, dont
     l'environnement contient toutes les dépendances.
- **Correctif** : test déplacé dans `tests/unit` (job `tests`).
- **Mesure préventive** : test `tests/security/test_bibliotheque_standard.py`, lancé par le
  job `exceptions`, qui refuse tout import hors de la bibliothèque standard dans ce dossier,
  avec un message qui renvoie vers `tests/unit`. Règle : un test est lancé localement comme le
  lance son job de CI.
- **Références** : PR #54.

### LL-032 — Retour après connexion vers un autre site possible (2026-10-08) — Close

- **Contexte** : alerte CodeQL (`py/url-redirection`) sur la PR #53, code venu de #52 ;
  jamais déployé.
- **Symptôme** : le chemin de retour après connexion (anomalie 3, LL-030) acceptait un
  chemin contenant un caractère blanc, que les navigateurs retirent d'une adresse : le
  chemin pouvait alors désigner un autre site.
- **Causes racines** :
  1. Pourquoi ? `chemin_local` refusait une liste de motifs connus (`//`, barre inverse,
     fins de ligne) au lieu de n'accepter qu'une forme sûre.
  2. Pourquoi non vu ? Les tests reprenaient les mêmes motifs que le code ; l'alerte
     CodeQL n'apparaît qu'en commentaire de PR, le contrôle restant vert (même famille que
     LL-003).
- **Correctif** : tout blanc et toute barre inverse refusés ; chemin ni schéma ni hôte
  après analyse (forme reconnue par CodeQL). Redirection de la page de choix faite avec le
  code de la liste des rapports, pas celui de la requête.
- **Mesure préventive** : test `test_retour_jamais_vers_un_autre_site` (tabulation,
  espace). Règle : toute alerte CodeQL d'une PR est lue et traitée avant la fusion, même
  avec des contrôles verts.
- **Références** : PR #52, #53.

### LL-031 — Défauts d'interface découverts en production, après fusion (2026-10-08) — Close

- **Contexte** : premiers usages en production (v0.1.1) par le mainteneur.
- **Symptôme** : quatre anomalies d'interface relevées à l'usage, après fusion et
  déploiement : aucun menu, commune cherchée par code postal seulement, heures en UTC
  (LL-029), erreur après une longue inactivité (LL-030). Les PR avaient des tests verts et un
  essai dans un navigateur.
- **Causes racines** :
  1. Pourquoi non vu avant la production ? Seul l'auteur des PR (l'agent) avait utilisé les
     pages, en suivant le contrat ; personne n'avait essayé les parcours réels de l'usager.
  2. Pourquoi ? Aucune étape ne demandait au mainteneur d'essayer les interfaces avant de
     fusionner : sa revue portait sur le code et la description de la PR.
  3. Pourquoi ? Essayer en local demandait de tout préparer à la main (base, stockage,
     rapport, comptes, lien de connexion), sans procédure écrite.
- **Correctif** : interfaces de #52 et #53 essayées par le mainteneur en local avant leur
  fusion ; trois retours dès le premier essai, corrigés dans #53 : liens peu visibles,
  résultat de recherche mal relié à la recherche, rang des points numéroté deux fois.
- **Mesure préventive** : `scripts/essai/lancer.sh` (base, stockage simulé, rapport figé de
  Courbevoie, serveur, lien de connexion affiché dans la console, compte mainteneur) ; README,
  section Développement. Règle : toute PR qui ajoute ou modifie une page porte, dans ses
  actions humaines, « essai des interfaces par le mainteneur avant fusion » avec la liste des
  pages à essayer ; le mainteneur ne fusionne qu'après cet essai.
- **Références** : PR #52, #53.

### LL-030 — Erreur en naviguant après être resté longtemps sur une page (2026-10-07) — Ouverte

- **Contexte** : premiers usages en production, signalé par le mainteneur (anomalie 3) ;
  non reproduit à ce jour.
- **Symptôme** : après un long moment sur une page, la navigation aboutit à une page
  d'erreur.
- **Causes racines** (hypothèses, non vérifiées) :
  1. Session expirée ou absente : page « Connexion requise » sans lien de connexion ni
     retour à la page voulue.
  2. Nouvelle connexion dans un autre onglet : le jeton CSRF des formulaires restés ouverts
     n'est plus valable (« Formulaire expiré »).
  3. Vérification anti-robot expirée (10 min) au moment d'envoyer un formulaire.
  Dans tous les cas, la page d'erreur ne proposait que « Retour à l'accueil ».
- **Correctif** : page HTML sans session ⇒ accueil avec « session expirée », puis retour à
  la page voulue après la connexion (cookie de 15 min, chemin local seulement) ; page
  d'erreur avec « Revenir à la page précédente » (même site seulement).
- **Mesure préventive** : tests `test_page_protegee_sans_session_renvoie_vers_la_connexion`,
  `test_retour_a_la_page_demandee_apres_connexion`, `test_retour_jamais_vers_un_autre_site`,
  `test_page_d_erreur_propose_la_page_precedente`. Reste ouverte jusqu'à reproduction (message
  exact et page) ou absence de récidive.
- **Piste nouvelle (2026-10-09)** : quatrième cause possible, non envisagée jusque-là, la
  connexion à la base coupée par sa mise en veille et redonnée par le pool (LL-034) : même
  symptôme (erreur après un long moment, puis rechargement réussi). Corrigée avec LL-034.
- **Références** : branche `fix/interface-heure-session`.

### LL-029 — Heures affichées en UTC (2026-10-07) — Close

- **Contexte** : premiers usages en production (anomalie 2 du mainteneur).
- **Symptôme** : heures (suivi, demandes, relevés, modération) décalées de 1 à 2 h.
- **Causes racines** :
  1. Pourquoi ? Dates mises en forme par le serveur (`strftime`, `astimezone()` sans fuseau,
     ou chaînes ISO tronquées), alors que le conteneur tourne en UTC.
  2. Pourquoi non vu ? En local, le poste est à l'heure de Paris : `astimezone()` donnait la
     bonne heure ; les tests ne vérifiaient aucune heure affichée.
- **Correctif** : module `heure` (heure de Paris), filtre `heure` des gabarits pour toutes
  les dates affichées ; date du rapport et du parcours en heure de Paris ; date des relevés
  du rapport par le navigateur.
- **Mesure préventive** : tests `tests/unit/test_heure.py` (été, hiver, chaîne ISO, valeur
  sans fuseau, filtre). Règle : aucune date affichée sans le filtre `heure`.
- **Références** : branche `fix/interface-heure-session`.

### LL-028 — Orthophotos et infrarouge IGN en échec depuis Scaleway (2026-10-07) — Ouverte

- **Contexte** : premiers rapports de production (Courbevoie, Asnières).
- **Symptôme** : 26 points P1 par commune « âge de l'enrobé non évalué (orthophotos
  indisponibles) » ; à Asnières, 10 avertissements « Infrarouge indisponible pour F… ». Les
  mêmes lectures, rejouées depuis le poste de développement, réussissent toutes (6/6).
- **Causes racines** :
  1. Pourquoi ? Inconnue : l'erreur était avalée sans son type ni son détail ; hypothèse non
     vérifiée, limitation de débit de l'IGN sur l'adresse de sortie partagée de Scaleway.
  2. Pourquoi inconnue ? Le code ne gardait ni la cause ni le nombre d'échecs, et le
     diagnostic par une exécution ponctuelle du job n'a pas été mené (à faire par le
     mainteneur, action sur la production).
- **Correctif** : cause de chaque échec (`sources.base.cause` : « Orthophotos IGN : HTTP
  429 », ou type de l'exception, jamais son message) dans la raison du « non évalué » et
  dans un avertissement regroupé par étape (nombre, causes, points).
- **Mesure préventive** : tests `test_orthophotos_en_echec_tracees_avec_leur_cause`,
  `test_orthophotos_indisponibles_signalees_dans_le_rapport`. Reste ouverte : correctif de
  la cause, une fois connue grâce au premier rapport produit avec cette version.
- **Références** : branche `fix/moteur-paris-ign-ia`.

### LL-027 — Aucun point pour un arrondissement de Paris (2026-10-07) — Close

- **Contexte** : premier rapport de production pour Paris 17e (75117).
- **Symptôme** : « Aucun point à relever : aucune ligne de bus desservant la commune. »
- **Causes racines** :
  1. Pourquoi ? L'offre IDFM est demandée avec `code_commune="75117"` et ne renvoie rien.
  2. Pourquoi ? IDFM rattache toute l'offre de Paris à la commune `75056` (vérifié :
     88 420 lignes ; aucun code `751xx`).
  3. Pourquoi non vu ? Fixtures et essais limités aux Hauts-de-Seine (Courbevoie).
- **Correctif** : `idfm.code_commune_offre` : `75056` pour un arrondissement ; les arrêts
  restent limités au contour de l'arrondissement (`points.arrets`).
- **Mesure préventive** : tests `test_offre_d_un_arrondissement_de_paris`,
  `test_offre_d_un_arrondissement_demandee_pour_paris`. Règle : toute source filtrée par
  code commune est vérifiée sur un arrondissement de Paris.
- **Références** : branche `fix/moteur-paris-ign-ia`.

### LL-026 — IA jamais appelée en production, sans alerte (2026-10-07) — Close

- **Contexte** : premiers rapports de production (Courbevoie, Asnières), relus par le
  mainteneur ; défaut découvert dans `points.geojson`, aucun avertissement ne le signalait.
- **Symptôme** : `ia.appels = 0` dans le journal des rapports ; 10 à 14 points P1 par
  commune « non évalués (service indisponible : PermissionDeniedError) ».
- **Causes racines** :
  1. Pourquoi ? L'API de l'IA répond 403 à la clé de `bitumap-job` sur
     `https://api.scaleway.ai/v1` et 200 sur `https://api.scaleway.ai/<projet>/v1`
     (vérifié avec la clé du job, liste des modèles et chat).
  2. Pourquoi ? Une application dont la politique est limitée à un projet doit nommer le
     projet dans l'adresse ; l'évaluation des modèles (R7) avait été faite avec une clé
     de portée organisation, qui n'a pas ce besoin.
  3. Pourquoi non vu ? La CI simule l'IA (T094 ouverte) ; un échec d'appel ne produit qu'un
     facteur « non évalué », ni avertissement dans le rapport ni alerte au mainteneur.
- **Correctif** : `BITUMAP_IA_URL` du projet passé au job par OpenTofu (`job.tf`).
- **Mesure préventive** : avertissement regroupé dans le rapport (nombre, cause, points)
  et alerte au mainteneur une fois par jour quand le service d'IA échoue (tests
  `test_ia_indisponible_signalee`, `test_alerte_ia_une_fois_par_jour`,
  `test_echec_du_service_trace_avec_sa_cause`). Règle : tout service appelé avec une clé
  d'exécution est essayé avec **cette** clé avant la mise en service.
- **Références** : PR #50 (`fix/ia-url-projet`), branche `fix/moteur-paris-ign-ia`.

### LL-025 — Domaine d'envoi créé mais marqué « tainted » (2026-10-07) — Close

- **Contexte** : apply suivant #46 par le mainteneur (bootstrap relancé, offre TEM
  souscrite).
- **Symptôme** : `waiting for Domain failed: … resource domain with ID … is not found` sur
  `scaleway_tem_domain.envoi`. Le domaine existait pourtant (`unchecked`, bon projet) et se
  lisait sans erreur quelques minutes plus tard ; OpenTofu l'avait marqué `tainted`, et le
  plan suivant voulait le **détruire et le recréer**. Ce plan voulait aussi retirer du job
  un `retry_policy` que Scaleway renseigne à 0.
- **Causes racines** :
  1. Pourquoi ? Le fournisseur 2.84 lit le domaine aussitôt après sa création ; l'API
     ne le connaît pas encore (cohérence différée) et répond 404, ce que l'attente traite
     comme une erreur.
  2. Pourquoi « tainted » ? Toute erreur après la création d'une ressource la marque
     ainsi, même si elle est saine.
  3. Pourquoi le job ? Bloc `retry_policy` omis, donc vu comme absent face à la valeur
     renseignée par Scaleway (même famille que la mémoire du conteneur, LL-024).
- **Correctif** : `tofu untaint scaleway_tem_domain.envoi` après vérification de son
  existence (mainteneur) ; `retry_policy { max_retries = 0 }` déclaré. Le plan suivant a
  révélé un autre défaut : la sortie `dns_courriel` ajoutait le domaine et un point à
  `dkim_name`, `dmarc_name` et `mx_config`, déjà complets (`….fr..courriel…`) ; elle les
  reprend désormais tels quels. Les enregistrements DNS, relevés dans l'API, étaient justes.
- **Mesure préventive** : conduite à tenir dans `infra/tofu/README.md`. Règle de LL-024
  confirmée : un plan relancé juste après l'apply doit être vide ; tout écart est corrigé
  dans le code, pas accepté.
- **Références** : branche `fix/job-retry-tem-attente`.

### LL-024 — Apply interrompu : offre TEM absente, disque du job hors limite (2026-10-07) — Close

- **Contexte** : premier `tofu apply` de la PR C (#45) par le mainteneur.
- **Symptôme** : apply arrêté après 4 créations sur 6 : `403 Forbidden: No active offer
  subscription for the project` (domaine d'envoi) et `local storage capacity must be greater
  than 1000 and lower than 10240 MiB` (job). Le plan suivant voulait aussi modifier la mémoire
  du conteneur, qui venait d'être créé (1 073 741 824 → 1 073 000 000 octets).
- **Causes racines** :
  1. Pourquoi ? Transactional Email exige un abonnement du projet à une offre, que le
     fournisseur OpenTofu ne sait que lire ; le job demandait 20 Gio de disque, au-delà du
     maximum de Scaleway ; Scaleway arrondit la mémoire au Mo décimal.
  2. Pourquoi non vu au plan ? `tofu plan` ne vérifie que le schéma du fournisseur, pas les
     règles de l'API (bornes, abonnements) : seul l'apply les rencontre.
  3. Pourquoi non vu à la revue ? Valeurs choisies sans relire les limites publiées du
     service ; l'abonnement n'apparaît dans aucune ressource du fournisseur.
- **Correctif** : offre `essential` souscrite par le bootstrap (étape 6) ; source
  `scaleway_tem_offer_subscription` et précondition sur le domaine d'envoi, qui arrête le
  **plan** avant toute création (la source renvoie `null` sans abonnement, pas une erreur) ;
  disque du job à 10 000 Mio ; mémoire du conteneur en Mo décimaux.
- **Mesure préventive** : précondition ci-dessus, rejouée sur le projet réel (plan arrêté
  avec le message attendu). Règle : toute nouvelle ressource Scaleway a ses limites
  (bornes, prérequis de compte) relevées dans la documentation du service avant la PR, et
  un plan relancé juste après l'apply doit être vide.
- **Références** : PR #45, branche `fix/tem-offre-stockage-job`.

### LL-023 — Le job n'aurait jamais démarré sur Scaleway (2026-10-07) — Close

- **Contexte** : écriture du job Scaleway (`infra/tofu/job.tf`, T081, branche
  `002-conteneurs`), avant tout déploiement ; défaut présent sur `main` depuis la PR #14.
- **Symptôme** (prévisible, reproduit) : configuration chargée avec les seuls secrets du
  job ⇒ `ValidationError` de pydantic, `altcha_hmac` et `sel_origine` « Field required ».
  Chaque lancement planifié (96 par jour) se serait arrêté avant toute action, sans
  alerte au mainteneur (l'alerte lit la même configuration).
- **Causes racines** :
  1. Pourquoi ? `Reglages` déclarait obligatoires tous les secrets, y compris ceux que seule
     l'API utilise (antibot, empreinte des adresses IP, pseudonymes).
  2. Pourquoi non vu ? Les tests, le compose local et le lancement de l'image du job
     (LL-022) fournissaient le même jeu complet de variables ; aucun ne jouait le job avec
     ses seuls secrets.
  3. Pourquoi ce jeu complet ? Les secrets de chaque composant n'ont été séparés qu'à
     l'écriture de la définition du job (moindre privilège).
- **Correctif** : `altcha_hmac` et `sel_origine` facultatifs dans la configuration ; l'API
  refuse de démarrer sans eux (`verifier_secrets_api`, au démarrage du serveur) ; le job ne
  les reçoit pas.
- **Mesure préventive** : tests `test_le_job_demarre_sans_les_secrets_de_l_api`,
  `test_l_api_refuse_de_demarrer_sans_ses_secrets`. Règle : tout point d'entrée d'image est
  lancé avec **exactement** les variables que lui donne OpenTofu, pas celles du `.env`.
- **Récidive en production (2026-10-07)** : le job déployé échoue à chaque passage depuis
  12 h (heure de Paris), avec la même erreur. Le correctif est arrivé avec #45, après le tag
  `v0.1.0` : les digests déployés désignaient des images qui ne le contenaient pas
  (reproduit en reconstruisant l'image du tag). Correction : version `v0.1.1`, digests mis
  à jour. Règle : un correctif de code n'est en production qu'après une nouvelle version
  **et** la mise à jour des digests ; la PR qui le livre le rappelle dans ses actions
  humaines.
- **Références** : branche `002-conteneurs`.

### LL-022 — Trace d'erreur à chaque fin du job de lot (2026-10-06) — Close

- **Contexte** : développement de T096 (branche `002-images-et-job`), premier lancement de
  l'image `job` contre la base et le S3 locaux ; défaut présent sur `main`, rien de déployé.
- **Symptôme** : à chaque fin de job ayant ouvert la base, code de sortie 0 mais trace
  `PythonFinalizationError: cannot join thread at interpreter shutdown`
  (`ConnectionPool.__del__`) dans la sortie. En production, chaque lot aurait laissé une
  erreur dans Cockpit, de quoi masquer les vraies.
- **Causes racines** :
  1. Pourquoi ? Le pool de connexions de psycopg n'était jamais fermé : son destructeur
     s'exécute pendant l'arrêt de l'interpréteur et tente de joindre ses fils, ce que
     Python 3.14 interdit à ce stade.
  2. Pourquoi non vu ? Les tests appellent `executer()` dans le processus de pytest, qui
     ferme le pool à la fin de la session ; le job n'avait jamais été lancé comme un
     processus réel, dans son image.
- **Correctif** : `main()` ferme le pool (`fermer_pool`) dans un `finally`.
- **Mesure préventive** : test `test_le_job_ferme_le_pool_avant_de_sortir` ; image du job
  lancée contre la base et le S3 locaux avant la PR (sortie sans trace). Règle : tout point
  d'entrée d'image est lancé au moins une fois dans son image avant sa PR.
- **Références** : branche `002-images-et-job`.

### LL-021 — Backend OpenTofu pointé sur le bucket d'un tiers (2026-10-06) — Close

- **Contexte** : première mise en œuvre d'`infra/tofu` par le mainteneur (PR A de la phase 7
  de 002, #42), poste local ; aucune donnée exposée.
- **Symptôme** : après `tofu init`, `.terraform/terraform.tfstate` désignait le bucket
  `yes`, qui existe chez Scaleway, appartient à un tiers et est lisible publiquement. Le
  premier plan enregistré utilisait aussi `application_tofu` = UUID nul (valeur du modèle) :
  appliqué, il aurait réservé l'administration des buckets à une application inexistante et
  enfermé OpenTofu hors de ses propres buckets.
- **Causes racines** :
  1. Pourquoi « yes » ? `terraform.tfvars` n'existait pas encore : `tofu init` a demandé
     `var.bucket_etat`, et la réponse a été prise pour une confirmation.
  2. Pourquoi accepté ? OpenTofu configure le backend avant de valider les variables
     (vérifié : un bloc `validation` n'agit qu'au `plan`) ; et le README ne demandait pas
     `-input=false`.
  3. Pourquoi l'UUID nul ? Le modèle `terraform.tfvars.example` ne disait pas où trouver
     l'identifiant de l'application IAM, confondu avec celui du projet, et aucune variable
     n'était validée. Le plan enregistré avant la correction l'aurait conservé.
  4. Pourquoi non vu en revue ? La validation locale (`fmt`, `validate`, Trivy) n'exécute
     ni `init` avec backend ni `plan` : la mise en œuvre humaine n'avait jamais été jouée.
- **Correctif** : état réinitialisé sur le bon bucket (`tofu init -reconfigure`),
  `application_tofu` corrigée, nouveau plan enregistré puis appliqué ; plan de contrôle
  sans changement.
- **Mesure préventive** : `identifiants-etat.sh` refuse de s'exécuter sans
  `terraform.tfvars`, avec un `bucket_etat` hors du format du bootstrap ou absent du projet ;
  validations de `bucket_etat` et `application_tofu` (format, UUID nul) dans `variables.tf` ;
  README : `tofu init -input=false`, `plan -input=false`, où trouver l'identifiant de
  l'application, refaire le plan après toute modification des variables. Essais rejoués
  sans réseau (conteneur `--network none`). Règle : toute procédure humaine d'infrastructure
  est jouée de bout en bout (init, plan) sur une copie avant sa PR.
- **Références** : PR #42, branche `fix/tofu-garde-fous-variables`.

### LL-020 — Tests en échec sur la première PR Dependabot : secret absent (2026-10-02) — Close

- **Contexte** : CI, PR #39 (Dependabot, digests `chainguard/python`), première PR
  Dependabot à déclencher le workflow `tests`.
- **Symptôme** : le job `tests` échoue avant toute étape : `Database is uninitialized and
  superuser password is not specified` (conteneur de service Postgres).
- **Causes racines** :
  1. Pourquoi ? `POSTGRES_PASSWORD` était vide : `secrets.CI_POSTGRES_PASSWORD` ne renvoyait
     rien.
  2. Pourquoi vide ? GitHub ne transmet aux exécutions déclenchées par Dependabot ni les
     secrets Actions ni ceux d'environnement (`ci-tests`) : seuls les secrets **Dependabot**
     sont lus.
  3. Pourquoi non vu plus tôt ? Le secret a été rangé dans `ci-tests` (revue de la PR #14)
     sans prévoir les PR Dependabot ; aucune n'avait encore lancé `tests`. Le message, au
     fond des journaux du conteneur, ne nommait pas le secret.
- **Correctif** : secret `CI_POSTGRES_PASSWORD` (valeur aléatoire distincte) déclaré dans les
  secrets Dependabot du dépôt par le mainteneur.
- **Mesure préventive** : job préalable `secret-base-de-test` dans `tests.yml`, qui échoue
  avec un message explicite si le secret est vide (les conteneurs de service démarrent avant
  toute étape du job `tests`). Règle : tout secret lu par un workflow déclenché sur
  `pull_request` est déclaré aussi dans les secrets Dependabot.
- **Références** : PR #39, branche `fix/ci-secrets-dependabot`.

### LL-019 — Liens de fichiers tiers suivis sans contrôle (2026-10-01) — Close

- **Contexte** : revue de sécurité de 004 (T044), avant toute mise en service de la 2.0 ;
  défaut latent, aucune exploitation (rien n'est déployé).
- **Symptôme** : trois sources de la 2.0 (température de surface, comptages du réseau
  national, Météo-France) téléchargeaient ou ouvraient des fichiers dont l'adresse est lue
  dans la réponse d'un service tiers, sans vérifier ni le schéma ni l'hôte, et sans borner la
  taille du téléchargement.
- **Causes racines** :
  1. Pourquoi ? Pour ne pas écrire de nom de fichier en dur (revue de la PR #33), les
     adresses sont découvertes dans les réponses des catalogues (STAC, data.gouv.fr).
  2. Pourquoi sans contrôle ? Le socle `obtenir` vérifiait les erreurs et les nouvelles
     tentatives, pas l'origine des adresses ; une adresse découverte a été traitée comme une
     constante du code.
  3. Pourquoi non vu plus tôt ? La revue de sécurité de 004 était prévue en fin de
     fonctionnalité (T044) ; les PR #33 et #34 n'ont pas eu de revue de sécurité propre.
- **Correctif** : `sources.base.verifier_url` (HTTPS et hôte attendu par source) avant tout
  téléchargement ou ouverture par GDAL ; `sources.base.telecharger` (taille annoncée et réelle
  bornée, nouvelles tentatives).
- **Mesure préventive** : tests `test_telechargement.py`,
  `test_lien_de_scene_hors_de_la_collection_refuse`, `test_archive_hors_de_data_gouv_refusee`.
  Règle : toute adresse lue dans une réponse tierce passe par `verifier_url` ; tout fichier
  téléchargé passe par `telecharger` avec une taille maximale ; toute PR ajoutant un appel
  réseau a sa revue de sécurité, sans attendre la fin de la fonctionnalité.
- **Références** : branche `004-finitions` (T044).

### LL-018 — % de poids lourds publié multiplié par 10 (2026-10-01) — Close

- **Contexte** : développement de 004 (US3, poids lourds), lecture des millésimes du trafic
  moyen journalier du réseau routier national (data.gouv.fr) avant d'écrire l'adaptateur.
- **Symptôme** : dans le millésime 2019, 76 sections non concédées d'Île-de-France ont un
  « % de poids lourds » au-dessus de 100 (A86 : 120, N4 : 327) ; la N13 passe de 4,6 % en 2018
  à « 46 » en 2019. Utilisée telle quelle, la valeur aurait donné l'effet maximal à ces
  voies.
- **Causes racines** :
  1. Pourquoi ? Le producteur a publié pour ces sections une valeur dix fois trop grande
     (virgule décimale perdue, vraisemblablement) ; les autoroutes concédées du même fichier
     sont justes.
  2. Pourquoi aurait-on pu l'utiliser ? L'inventaire T003 notait le champ et la licence, pas
     la plage des valeurs ; et depuis 2022 seul le réseau concédé est publié, 2019 était donc
     le « dernier millésime » du réseau non concédé.
  3. Pourquoi vu à temps ? Les valeurs ont été comparées d'un millésime à l'autre avant
     d'écrire le code (même famille que LL-016 : vérifier une source sur des données réelles).
- **Correctif** : dernier millésime publié seulement (réseau non concédé « non évalué »,
  décision du mainteneur) ; garde-fou : un % de poids lourds hors de ]0, 100] écarte la
  section.
- **Mesure préventive** : test `test_reseau_national_dernier_millesime` (section à % fautif
  écartée). Règle : toute nouvelle source chiffrée est contrôlée sur sa plage de valeurs et
  comparée à un autre millésime avant d'être utilisée.
- **Références** : branche `004-us3-poids-lourds`, research R5.

### LL-017 — Feux dessinés hors de la commune sur la carte du rapport (2026-09-30) — Close

- **Contexte** : relecture de la carte du rapport de Courbevoie par le mainteneur.
- **Symptôme** : des losanges (carrefours à feux) apparaissent hors de la commune et loin
  des voies de bus ; mesuré dans un navigateur : 58 feux sur 58 déplacés, de 266 px en
  médiane (418 px au plus). Les données des points étaient justes (un seul point sur la
  limite communale).
- **Causes racines** :
  1. Pourquoi ? Chaque losange était un carré tourné par l'attribut
     `transform="rotate(45 x y)"`.
  2. Pourquoi déplacé ? La règle CSS `.pt{transform-box:fill-box}`, ajoutée pour agrandir
     le point sélectionné autour de son centre, change le repère de cet attribut : le
     centre de rotation (x, y) est compté depuis le coin du losange, pas depuis l'origine
     de la carte.
  3. Pourquoi non vu ? Les tests vérifiaient le contenu du SVG (points présents, formes),
     jamais la position rendue ; les cercles, sans rotation, étaient bien placés.
- **Correctif** : losange tracé par ses quatre sommets (`polygon`), sans attribut
  `transform`.
- **Mesure préventive** : test `test_feux_a_leur_place_sur_la_carte` (aucun `transform` sur
  un point de la carte ; centre de chaque losange à la position projetée du feu) ; mesure
  dans un navigateur des positions rendues (58/58 à 0 px, sélection comprise). Règle : un
  changement de CSS sur un élément SVG est vérifié sur le rendu, pas sur le code.
- **Références** : défaut introduit par 33ab279 (PR #17, sélection visible) ; branche
  `fix/carte-losanges-feux`.
### LL-016 — Ombres fictives du LiDAR malgré des tests verts (2026-09-30) — Close

- **Contexte** : développement de 004 (US1, ensoleillement sur LiDAR HD), première exécution
  de la méthode 2.0 sur les données figées de Courbevoie, avant la PR.
- **Symptôme** : tous les tests (grilles synthétiques) passaient, mais sur Courbevoie des
  carrefours passaient de 10 h à 1,3 h de soleil, « à cause de bâtiments » absents de la
  BD TOPO ; la cause « arbre » ne sortait que 6 fois sur 154 points.
- **Causes racines** :
  1. Pourquoi ? Le MNS contient tout ce que le laser a touché : véhicules présents lors du
     survol (2 à 3 m au bord des points de mesure), mâts de feux et lampadaires (8 à 16 m à
     2 m des feux) ; à 2 m, un tel objet cache le soleil jusqu'à 57° de hauteur.
  2. Pourquoi « arbre » si rare ? L'infrarouge manque les arbres à l'ombre des immeubles
     (avenue Gambetta) et le bord des toits tombe à 1 m hors de l'emprise BD TOPO.
  3. Pourquoi non vu par les tests ? Les grilles synthétiques ne contenaient que ce que
     l'on y mettait : des bâtiments et des arbres idéaux (même famille que LL-003 :
     vérifier l'effet sur les données réelles, pas seulement la forme).
- **Correctif** : ouverture morphologique du sursol (objets de moins de 3 m de large
  effacés), sursol de moins de 4 m ramené au sol, cause « arbre » par la végétation à 1 m
  près ou la rugosité du sursol (5 × 5 m), emprises BD TOPO élargies d'un mètre pour le
  classement. Chaque cas vérifié sur l'orthophoto et l'ombrage du MNH.
- **Mesure préventive** : tests `test_vehicule_du_survol_ignore`, `test_mat_de_feu_ignore`,
  `test_houppier_rugueux_classe_arbre_sans_infrarouge`,
  `test_construction_lisse_non_repertoriee_classe_batiment` ;
  `tests/non_regression/test_courbevoie_v2.py` sur les données figées réelles. Règle : toute
  nouvelle source mesurée est passée sur une commune réelle et ses plus grands écarts sont
  examinés sur image avant la PR.
- **Références** : branche `004-us1-ensoleillement-lidar`.

### LL-015 — Hook de protection de main inactif hors de /mnt/c (2026-09-30) — Close

- **Contexte** : préparation du déplacement du dépôt de `/mnt/c` (disque Windows, dossier
  kDrive exclu) vers le disque natif de WSL ; inventaire avant migration.
- **Symptôme** (prévisible, non observé en usage) : les 21 fichiers versionnés commençant par
  `#!`, dont `.claude/hooks/guard-main.sh`, étaient en mode `100644`. Rejoué depuis le disque
  natif, le hook répond `permission denied` (code 126) ; Claude Code traite ce code comme une
  erreur non bloquante : un `git push origin main` n'aurait plus été refusé par le hook.
- **Causes racines** :
  1. Pourquoi ? Le bit d'exécution n'a jamais été enregistré dans git pour ces scripts.
  2. Pourquoi non vu ? Sous `/mnt/c`, WSL présente tous les fichiers en `rwxrwxrwx` et
     `core.filemode` vaut `false` : les scripts s'exécutaient et git ne voyait aucun écart.
  3. Pourquoi aucun contrôle ? Aucun test ne vérifiait le mode des scripts ; les interdictions
     de `.claude/settings.json` (push sur main, fusion de PR) masquaient en partie l'absence
     du hook.
- **Correctif** : `git update-index --chmod=+x` sur les 21 fichiers commençant par `#!`.
- **Mesure préventive** : test `tests/unit/test_scripts_executables.py` (tout fichier suivi
  commençant par `#!` est en `100755`, et le hook de protection de main en particulier),
  exécuté en CI sur un système de fichiers Linux. Règle : un script ajouté sous `/mnt/c`
  passe par `git update-index --chmod=+x` ; le dépôt de travail est à déplacer sur le disque
  natif de WSL.
- **Références** : branche `chore/bits-execution-scripts`.

### LL-014 — Une photo retirée pouvait être renvoyée sous le même identifiant (2026-09-30) — Close

- **Contexte** : revue de sécurité de 003 (T042), branche de la modération (US5) ; défaut
  présent depuis le MVP (#24), trouvé avant toute mise en production.
- **Symptôme** (prévisible, non observé) : après le retrait d'une photo, par son auteur ou
  par le mainteneur (RGPD), l'auteur pouvait redemander un formulaire d'envoi pour le même
  identifiant, déposer une autre image et la confirmer : la photo redevenait `visible`,
  annulant le retrait (FR-016).
- **Causes racines** :
  1. Pourquoi ? `formulaire` acceptait un identifiant existant quel que soit son état, et
     `confirmer` ne distinguait que « visible » (rejeu) du reste, traité comme une
     quarantaine.
  2. Pourquoi ? L'idempotence (réenvoi depuis un téléphone hors réseau) a été pensée pour
     deux états, `quarantaine` et `visible` ; les états de retrait, ajoutés ensuite, n'ont pas
     été rapprochés des chemins d'envoi.
  3. Pourquoi non vu ? Les tests de retrait vérifiaient l'effet du retrait, jamais une
     tentative d'envoi postérieure ; la mise à jour finale n'avait pas de garde sur l'état
     (course possible entre retrait et confirmation).
- **Correctif** : `409 photo_retiree` au formulaire et à la confirmation d'une photo
  retirée (quarantaine effacée) ; mise à jour `… AND etat = 'quarantaine'`, et, si la photo a
  été retirée entre-temps, suppression de toutes les versions de l'objet écrit. Le rejeu
  d'une photo `visible` efface aussi la quarantaine redéposée.
- **Mesure préventive** : tests `test_photo_retiree_ne_peut_etre_renvoyee` (auteur, RGPD),
  `test_retrait_pendant_l_envoi`, `test_depot_rejoue_apres_succes`. Règle : tout état
  terminal (retrait, suppression) est testé contre chaque chemin d'écriture qui pourrait le
  faire revenir en arrière, rejeux idempotents compris.
- **Références** : branche `003-us5-moderation-finition`.

### LL-013 — Original d'une photo récupérable dans le bucket versionné (2026-09-30) — Close

- **Contexte** : développement de 003 (US5, modération), relecture du retrait RGPD ; défaut
  latent, trouvé avant toute mise en production (aucune donnée réelle).
- **Symptôme** : après réencodage d'une photo, l'original déposé en `quarantaine/` (avec ses
  métadonnées EXIF, dont la position GPS) restait lisible : la clé portait encore une
  version non courante et un marqueur de suppression (vérifié par une sonde sur le S3
  simulé).
- **Causes racines** :
  1. Pourquoi ? La quarantaine était effacée par un simple `delete_object`, qui, dans un
     bucket versionné, ajoute un marqueur de suppression sans détruire le contenu.
  2. Pourquoi ce choix ? Le versionnement du bucket `bitumap-terrain` (décidé pour
     l'historique) n'a pas été rapproché de l'effacement des données personnelles.
  3. Pourquoi non vu ? Les tests vérifiaient que la clé n'était plus lisible (`lire` →
     `None`), pas qu'aucune version n'existait (même famille que LL-003 : l'effet attendu
     n'était pas mesuré).
- **Correctif** : `stockage.effacer_definitivement` supprime toutes les versions et tous les
  marqueurs d'une clé ; utilisé pour la quarantaine et pour le retrait RGPD d'une photo.
- **Mesure préventive** : tests `test_original_non_conserve_par_le_versionnement` et
  `test_retrait_rgpd_d_une_photo` (aucune version restante) ; T040 : la règle de cycle de vie
  de `quarantaine/` expire aussi les versions non courantes. Règle : dans un bucket
  versionné, tout effacement de donnée personnelle supprime toutes les versions et est
  testé sur la liste des versions.
- **Références** : branche `003-us5-moderation-finition`.

### LL-012 — Constaté absent du rapport malgré des tests verts (2026-09-29) — Close

- **Contexte** : développement de 003 (US2), essai du parcours dans un navigateur (émulation
  mobile) avant la PR.
- **Symptôme** : un relevé saisi n'apparaît ni dans la synthèse « Constaté » ni dans la fiche
  du rapport ; aucune erreur en console. Les tests de `test_rapport_releves.py` passaient.
- **Causes racines** :
  1. Pourquoi ? Le script du rapport lit le bloc `releves` au chargement et ne le trouvait
     pas : il valait `{}`.
  2. Pourquoi ? L'API insérait le bloc juste avant `</body>`, donc **après** le script en
     ligne, qui s'exécute dès qu'il est analysé.
  3. Pourquoi non vu ? Les tests vérifiaient la présence et le contenu du bloc dans le HTML,
     pas qu'il soit lisible par le script (même famille que LL-003 : présent ≠ effectif).
- **Correctif** : le bloc est inséré juste après le bloc `donnees`, avant le script.
- **Mesure préventive** : test `test_bloc_avant_le_script_qui_le_lit` (ordre des blocs) ;
  le parcours navigateur du quickstart reste obligatoire avant chaque PR touchant le rapport
  ou la saisie.
- **Références** : branche `003-terrain-releves`.

### LL-011 — CSP d'un rapport en cache liée à la version courante du script (2026-09-29) — Close

- **Contexte** : conception de 003 (relevés terrain), rapport servi par l'API de 002 ;
  défaut latent, trouvé avant toute mise en production.
- **Symptôme** (prévisible, non observé) : après toute modification de
  `rapport/interactions.js` (PR #17, #19), un rapport encore en cache (30 jours), produit
  avec l'ancien script, serait servi avec une CSP n'autorisant que l'empreinte du **nouveau**
  script : filtres, fiche et carte inertes.
- **Causes racines** :
  1. Pourquoi ? `CSP_RAPPORT` était une constante calculée au démarrage sur le script du code
     en cours, alors que le script est figé dans chaque `rapport.html` stocké.
  2. Pourquoi non vu ? Les tests génèrent le rapport et le servent avec le même code ; aucun
     test ne servait un rapport produit par une version antérieure.
  3. Pourquoi pas d'incident ? Aucun rapport n'est encore en production.
- **Correctif** : `rapport.rendu.csp_du_document(html)` calcule, à chaque service,
  l'empreinte des scripts en ligne **du document servi** (analyseur HTML, blocs de données
  JSON exclus) ; le document vient du bucket privé, écrit par le job.
- **Mesure préventive** : `tests/api/test_rapport_csp.py` (ancien script autorisé, bloc JSON
  exclu, balise en majuscules reconnue, document sans script ⇒ `script-src 'none'`). Règle :
  tout artefact stocké et servi plus tard est testé avec une version antérieure du code.
- **Références** : branche `003-terrain-releves` (T006, T007).

### LL-009 — Coût IA du jour arrondi à chaque opération (2026-09-29) — Close

- **Contexte** : développement US4, test du plafond de coût par rapport
  (`tests/unit/test_journal.py`).
- **Symptôme** : dépense d'un rapport ≤ 0,002 €, mais cumul du jour enregistré à 0,0021 €.
- **Causes racines** :
  1. Pourquoi l'écart ? `cout_ia_jour.montant_eur` était en `numeric(10, 4)` : chaque
     réservation (≈ 0,0004 €) et chaque ajustement étaient arrondis au dix-millième.
  2. Pourquoi 4 décimales ? Choisies à l'échelle de l'euro, sans rapprocher du coût d'un
     appel (≈ 0,0003 €, R7-bis), du même ordre que la précision.
  3. Pourquoi non vu plus tôt ? Les tests du budget comparaient des plafonds larges au
     cumul, jamais le cumul du jour à la somme exacte des dépenses.
- **Correctif** : migration `002` : `numeric(12, 6)` pour `cout_ia_jour.montant_eur` et
  `lot.cout_ia_eur`.
- **Mesure préventive** : test du plafond serré (0,002 €) comparant le cumul du jour à la
  dépense réelle. Règle : la précision d'un montant stocké est choisie à partir de la plus
  petite opération (ici un appel), pas de l'unité affichée.
- **Références** : branche `002-us4-couts-suivi`.

### LL-008 — Arrêt sous un pont classé Critique (2026-09-29) — Close

- **Contexte** : méthode de score, rapport de Courbevoie, issue #18 ouverte par le mainteneur.
- **Symptôme** : « Verdun - Rue Latérale » (A27418) classé Critique (rang 4) avec « plein
  soleil l'été : 10,5 h/jour », alors que le bus s'arrête sous le pont ferroviaire de la ligne
  Saint-Lazare – Versailles.
- **Causes racines** :
  1. Pourquoi 10,5 h ? La grille d'ombres ne contenait que les bâtiments et les arbres ; les
     tabliers de ponts n'existaient pas pour le calcul.
  2. Pourquoi ignorés ? Méthode reprise du prototype, qui ne les modélisait pas, et la
     non-régression compare au prototype : elle ne pouvait pas révéler le défaut.
  3. Pourquoi ajouter les ponts ne suffisait pas (7,5 h) ? L'ensoleillement était mesuré en un
     seul point, projection du poteau, ici au bord du tablier ; or le bus s'arrête en amont
     du poteau, sous le pont.
- **Correctif** : méthode 1.2 : tabliers OSM dans la grille d'ombres, mesure d'un arrêt sur
  sa zone d'arrêt (12 m en amont, 5 points) ; A27418 : 1,5 h, rang 63, À surveiller.
- **Mesure préventive** : tests `tests/unit/test_ouvrages.py` (chaussée sous un pont, bus sur
  un pont, zone d'arrêt au bord du tablier) ; écarts SC-003 dus aux ponts documentés. Règle :
  un écart au prototype n'est pas une erreur en soi ; les relectures terrain du mainteneur
  (issues) priment sur la ressemblance au prototype.
- **Références** : issue #18, branche `002-issue-18-ouvrages`.

### LL-007 — Liens Panoramax du rapport vers une page sans photo (2026-09-29) — Close

- **Contexte** : relecture du rapport de Courbevoie par le mainteneur (fiche d'un point).
- **Symptôme** : le lien « Photo de rue du … » ouvre la page d'accueil de panoramax.fr, sans
  la photo.
- **Causes racines** :
  1. Pourquoi ? L'URL était `https://panoramax.fr/#focus=pic&pic=<id>` : panoramax.fr est le
     site vitrine du projet, pas une visionneuse ; il ignore ces paramètres.
  2. Pourquoi ce format ? Écrit par analogie avec les paramètres de la visionneuse, sans
     ouvrir une seule fois le lien produit.
  3. Pourquoi non détecté ? Les tests vérifiaient la présence d'un lien, pas sa cible ; les
     fixtures figées reproduisaient la même URL.
- **Correctif** : visionneuse du méta-catalogue `https://api.panoramax.xyz/#focus=pic&pic=<id>`
  (vérifiée dans un navigateur : la photo s'affiche) ; 65 URL des fixtures réécrites.
- **Mesure préventive** : test du format exact des liens (`tests/rapport/test_rendu.py`) ;
  règle : tout lien externe généré est ouvert au moins une fois dans un navigateur avant sa
  PR (même esprit que LL-003 : vérifier l'effet, pas seulement la forme).
- **Références** : branche `002-us3-us4-rapport-couts`.

### LL-006 — Port de la base locale réservé par Windows (2026-09-29) — Close

- **Contexte** : développement sous WSL2 avec Docker Desktop, reprise après redémarrage du
  poste, branche `002-us2-antibot-quotas`.
- **Symptôme** : `docker compose up -d db` échoue : `ports are not available: exposing port
  TCP 127.0.0.1:55432 … /forwards/expose returned unexpected status: 500`.
- **Causes racines** :
  1. Pourquoi l'échec ? Le port 55432 est dans une plage réservée par Windows
     (`netsh int ipv4 show excludedportrange protocol=tcp` : 55334–55433).
  2. Pourquoi réservée ? WinNAT/Hyper-V réserve des blocs de ports au démarrage, pris dans la
     plage dynamique (49152–65535), différents à chaque redémarrage.
  3. Pourquoi y était-on ? Les ports de `compose.yaml` (55432, 55000) avaient été choisis
     « hauts » pour éviter les conflits, sans tenir compte de la plage dynamique.
- **Correctif** : ports locaux déplacés hors de la plage dynamique (base 15432, S3 simulé
  15000) et rendus configurables : `BITUMAP_DB_PORT` et `BITUMAP_S3_PORT` dans `.env`, lus par
  `compose.yaml` et `tests/conftest.py` (aucun port en dur, revue de la PR #16).
- **Mesure préventive** : règle : tout port publié sur le poste est choisi sous 49152 ;
  en cas d'échec d'exposition, vérifier d'abord `excludedportrange`.
- **Références** : branche `002-us2-antibot-quotas`.

### LL-005 — Python local sans module bz2 (2026-09-28) — Close

- **Contexte** : développement, premiers tests utilisant le stockage objet simulé (moto).
- **Symptôme** : `ModuleNotFoundError: No module named '_bz2'` à l'import de moto.
- **Causes racines** :
  1. Pourquoi ? Le Python 3.14 du poste (`/usr/local/bin/python3`) a été compilé sans la
     bibliothèque bzip2.
  2. Pourquoi l'utilisait-on ? `uv` prend par défaut le premier Python trouvé sur le système ;
     rien n'imposait une version complète et identique pour tous.
- **Correctif** : fichier `.python-version` (3.14) et Python géré par uv
  (`uv python install 3.14`, `UV_PYTHON_PREFERENCE=only-managed uv sync`).
- **Mesure préventive** : `.python-version` versionné ; la CI (setup-python) et les images
  (Chainguard) utilisent déjà un Python complet ; procédure notée dans le README
  (section Développement).
- **Références** : branche `002-on-demand-report`.

### LL-004 — Un secret sur une branche bloquait toutes les PR (2026-09-28) — Close

- **Contexte** : CI, validation SC-001 avec 5 PR pièges (#6 à #10).
- **Symptôme** : le contrôle `secrets` échoue sur les 5 PR, alors que seule la #6 contient
  un secret.
- **Causes racines** :
  1. Pourquoi les autres PR échouent ? Gitleaks y trouve le secret de la branche
     `trap/secret`.
  2. Pourquoi le voit-il ? `actions/checkout` avec `fetch-depth: 0` récupère toutes les
     branches, et `gitleaks git` analyse par défaut `git log --all`.
  3. Pourquoi ce choix ? La spec (FR-003) demandait l'analyse de l'historique, sans préciser
     la portée par événement.
- **Correctif** : sur `pull_request`, Gitleaks n'analyse que `base.sha..head.sha` ; sur
  `main`, en hebdomadaire et à la demande, il garde l'historique complet de toutes les
  branches. Un secret poussé n'importe où reste détecté au plus tard sous 7 jours.
- **Mesure préventive** : test de portée (branche propre → 0, branche fautive → 1,
  historique complet → 1) documenté dans la PR ; comportement décrit dans
  `research.md` (R4) et `contracts/required-checks.md`.
- **Références** : PR #6 à #10 (fermées), branche `fix/gitleaks-pr-scope`.

### LL-003 — Rapports SARIF jamais publiés malgré des contrôles verts (2026-09-28) — Close

- **Contexte** : CI, première exécution de `security.yml` sur la PR #5.
- **Symptôme** : les 8 contrôles sont verts, mais Security → Code scanning ne contient que
  CodeQL ; les rapports Gitleaks, Trivy et zizmor n'ont pas été publiés, sans aucune erreur.
- **Causes racines** :
  1. Pourquoi pas publiés ? L'étape d'envoi était sautée : sa condition était fausse.
  2. Pourquoi fausse ? `hashFiles()` ne lit que l'espace de travail (`GITHUB_WORKSPACE`) ; les
     rapports étaient écrits dans `runner.temp`, donc `hashFiles` renvoyait toujours ''.
  3. Pourquoi écrits hors de l'espace de travail ? Le dépôt est monté en lecture seule dans
     les conteneurs de scan (choix de sécurité volontaire).
  4. Pourquoi non détecté en local ? actionlint et zizmor valident la syntaxe, pas la
     sémantique de `hashFiles` ; et un saut d'étape n'est pas un échec.
- **Correctif** : étape explicite `[ -s "$RUNNER_TEMP/<outil>.sarif" ]` exposant une sortie
  `present`, condition d'envoi sur cette sortie.
- **Mesure préventive** : le quickstart (§2) exige de vérifier, après chaque première
  exécution, que chaque outil apparaît dans la liste des analyses Code scanning
  (`gh api repos/aboigues/bitumap/code-scanning/analyses`). Règle générale : un contrôle
  vert ne prouve pas qu'il a produit son effet ; vérifier la sortie attendue.
- **Références** : PR #5.

### LL-002 — kDrive recrée les fichiers retirés par git (2026-09-28) — Close

- **Contexte** : développement, dépôt cloné dans un dossier synchronisé par kDrive,
  passage de la branche `001-security-ci-baseline` à `main`.
- **Symptôme** : les fichiers de `specs/001-security-ci-baseline/` réapparaissent (avec des fins
  de ligne CRLF) sur une branche où ils n'existent pas, et sont commités par erreur dans
  `chore/scaleway-bootstrap` ; supprimés, ils reviennent en moins de 20 s.
- **Causes racines** :
  1. Pourquoi réapparaissent-ils ? Le client kDrive interprète la suppression faite par
     `git switch` comme une divergence et restaure sa copie en ligne.
  2. Pourquoi a-t-on commité ? `git add -A` prend tout ce qui est non suivi, sans relecture de
     la liste avant le commit.
  3. Pourquoi le dépôt est-il dans kDrive ? Emplacement historique du dossier de travail ; la
     sauvegarde est en réalité assurée par GitHub.
- **Correctif** : fichiers retirés de la branche par un commit dédié (sans force-push,
  principe IX).
- **Mesure préventive** : le dossier du dépôt est **exclu de la synchronisation kDrive**
  (exclusion suivie d'un redémarrage de kDrive et de la fermeture des fichiers ouverts, sans
  quoi elle n'est pas appliquée). Vérifié par un aller-retour de branches sans recréation
  après 45 s. Toujours : n'ajouter que des chemins explicites (jamais `git add -A`) et relire
  `git status` avant chaque commit. Tout nouveau poste de travail : cloner hors de tout
  dossier synchronisé (OneDrive, kDrive, Dropbox…).
- **Références** : branche `chore/scaleway-bootstrap`, commit « fix: retirer les fichiers de la
  001 recréés par la synchronisation kDrive ».

### LL-001 — Arrêt silencieux du bootstrap Scaleway en relance (2026-09-28) — Close

- **Contexte** : développement, première relance de `infra/bootstrap/bootstrap.sh` pour
  vérifier son idempotence.
- **Symptôme** : la relance s'arrête après l'étape 3, sans message ni sortie JSON ; l'étape
  « bucket d'état » n'est pas exécutée.
- **Causes racines** :
  1. Pourquoi l'arrêt ? `jq` échoue (`startswith() requires string inputs`) et `set -e` +
     `pipefail` stoppent le script.
  2. Pourquoi `jq` échoue ? `scw object bucket list -o json` renvoie la clé `Name` (majuscule,
     format S3) et non `name` comme les autres commandes `scw`.
  3. Pourquoi ne l'a-t-on pas vu ? La première exécution crée le bucket sans passer par ce
     filtre (liste vide) ; seule la relance lit la liste.
  4. Pourquoi aucun message ? L'erreur `jq` était redirigée (`2>/dev/null`) et le script
     n'avait pas de piège `ERR`.
- **Correctif** : filtre `(.Name // .name)` ; piège `trap … ERR` + `errtrace` qui affiche la
  ligne et la commande en échec.
- **Mesure préventive** : tout script d'infrastructure DOIT avoir un piège `ERR` et être
  exécuté **deux fois** avant sa PR (idempotence), ce qui est désormais noté dans
  `infra/bootstrap/README.md`. Aucun doublon n'avait été créé : l'arrêt est survenu avant la
  création.
- **Références** : branche `chore/scaleway-bootstrap`.
