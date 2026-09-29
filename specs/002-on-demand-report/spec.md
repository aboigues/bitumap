# Feature Specification: Rapport de risque d'orniérage à la demande

**Feature Branch**: `002-on-demand-report`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Formulaire d'entrée qui valide le code postal, avec une protection antibot, avant de lancer la génération. Reprendre les aspects intéressants du prototype Courbevoie et compléter avec le type de route (départementale, communale, etc.). Périmètre de la fonctionnalité 002 dans le README : formulaire (code postal, choix de la commune, antibot) et génération du rapport pour une commune, avec le type de route et son gestionnaire."

## Contexte

Le prototype (`docs/reference/prototype-courbevoie-v2.html`) a été produit à la main pour
Courbevoie : 153 points (arrêts de bus, carrefours à feux, giratoires) classés en priorités
P1 / P2 / P3 selon la charge des bus, la sollicitation, le site, la chaleur et l'âge de
l'enrobé. Cette fonctionnalité rend ce diagnostic **reproductible et disponible à la
demande pour n'importe quelle commune d'Île-de-France**, sans intervention manuelle.

Hors périmètre, prévus ensuite (README, feuille de route) : relevés terrain (003), méthode v2
avec ensoleillement et îlots de chaleur revus et type de route intégré au score (004),
échelle du département et export PDF (005).

## User Scenarios & Testing *(mandatory)*

Acteurs :

- **Demandeur** : agent de collectivité, bureau d'études ou exploitant de réseau qui veut le
  diagnostic d'une commune.
- **Mainteneur** : responsable du service ; surveille coûts, quotas et incidents.

### User Story 1 - Obtenir le rapport d'une commune à partir d'un code postal (Priority: P1)

Le demandeur ouvre le service et se connecte avec son adresse e-mail en cliquant sur le
lien de connexion qu'il reçoit (sans mot de passe). Il saisit ensuite un code postal
d'Île-de-France, choisit la commune concernée si le code postal en couvre plusieurs, puis
demande le rapport. Si le rapport existe déjà, il l'obtient immédiatement ; sinon sa demande
rejoint une file d'attente traitée par lots à intervalle régulier, il voit sa position et
l'heure estimée, et il reçoit un e-mail quand le rapport est prêt.

**Why this priority**: c'est la raison d'être du service ; sans elle, rien d'autre n'a de
valeur.

**Independent Test**: se connecter par lien e-mail, saisir `92400`, lancer la génération, obtenir un rapport de Courbevoie
comparable au prototype (mêmes types de points, priorités, carte, fiches, méthode, sources).

**Acceptance Scenarios**:

1. **Given** un demandeur non connecté, **When** il saisit son adresse e-mail et valide
   la preuve antibot, **Then** il reçoit un lien de connexion à usage unique valable
   15 minutes ; en le suivant, il est connecté.
2. **Given** le code postal `92400`, **When** le demandeur connecté le saisit, **Then** la commune
   Courbevoie lui est proposée et il peut lancer la génération.
3. **Given** le code postal `95000`, **When** il le saisit, **Then** les 4 communes
   correspondantes lui sont proposées et il doit en choisir une avant de lancer la
   génération.
4. **Given** une demande placée en file d'attente, **When** le demandeur consulte son suivi,
   **Then** il voit sa position, l'heure estimée de traitement, puis l'étape en cours
   (acquisition, calcul, rapport) et, à la fin, un lien vers le rapport.
5. **Given** un rapport terminé, **When** la génération s'achève, **Then** le demandeur reçoit
   un e-mail qui contient uniquement le nom de la commune et un lien vers le rapport
   (connexion requise pour l'ouvrir) ; en cas d'échec, un e-mail l'en informe sans détail
   technique.
6. **Given** le demandeur a fermé la page, **When** il revient et se reconnecte,
   **Then** il retrouve la liste de ses générations, leur état et les rapports terminés.
7. **Given** un rapport déjà produit pour cette commune avec les mêmes sources et la même
   version de méthode, **When** un demandeur le redemande, **Then** le rapport existant est
   servi immédiatement, sans nouveau calcul ni coût.

---

### User Story 2 - Être protégé contre les abus (Priority: P1)

Le service refuse les saisies invalides et les demandes automatisées, et limite le nombre de
générations pour qu'un abus ne puisse ni saturer le service ni faire exploser son coût.

**Why this priority**: principe I (sécurité d'abord) et principe II (coût maîtrisé) ; une
génération consomme des ressources payantes, dont un modèle d'IA.

**Independent Test**: soumettre des codes postaux invalides, hors Île-de-France, des requêtes
sans preuve antibot et des rafales de demandes ; vérifier les refus et l'absence de
génération lancée.

**Acceptance Scenarios**:

1. **Given** une saisie qui n'est pas un code postal à 5 chiffres, **When** elle est
   envoyée, **Then** elle est refusée avec un message explicite, sans appel externe.
2. **Given** un code postal valide hors Île-de-France (ex. `69001`), **When** il est
   envoyé, **Then** il est refusé avec un message indiquant le périmètre couvert.
3. **Given** un code postal au bon format mais inexistant, **When** il est envoyé, **Then**
   il est refusé.
4. **Given** une demande de génération sans preuve antibot valide, ou avec une preuve déjà
   utilisée, **When** elle arrive, **Then** elle est refusée et aucune génération n'est
   lancée.
5. **Given** le quota de générations atteint (par compte ou global), **When** une nouvelle
   génération est demandée, **Then** elle est refusée avec l'heure à laquelle réessayer ;
   les rapports déjà en cache restent consultables.
6. **Given** une commune déjà en file d'attente ou en cours de génération, **When** une
   seconde demande arrive pour elle, **Then** elle est rattachée à la demande existante (les
   deux demandeurs sont prévenus) au lieu d'en créer une deuxième ; elle ne compte pas dans
   le quota du second demandeur.
7. **Given** un visiteur non connecté ou dont la session a expiré, **When** il tente de
   lancer une génération ou d'ouvrir un rapport, **Then** il est invité à se connecter et
   aucune génération n'est lancée.
8. **Given** des demandes répétées de lien de connexion (même adresse ou même origine),
   **When** la limite est dépassée, **Then** elles sont refusées ; la réponse est identique
   que l'adresse ait déjà un compte ou non (pas de fuite sur l'existence d'un compte).
9. **Given** un lien de connexion déjà utilisé ou expiré, **When** il est suivi, **Then** il
   est refusé et le demandeur peut en demander un nouveau.

---

### User Story 3 - Lire et exploiter le rapport (Priority: P1)

Le demandeur consulte un rapport qui reprend les apports du prototype : vue d'ensemble
chiffrée, carte des points, liste classée et filtrable, fiche détaillée de chaque point,
méthode, sources et limites. Chaque point indique en plus **le type de la route** (nationale,
départementale, communale, voie privée…) et **son gestionnaire**, pour savoir à qui
transmettre le rapport.

**Why this priority**: le rapport est le livrable ; son exploitabilité conditionne l'usage
terrain.

**Independent Test**: sur le rapport de Courbevoie, vérifier la présence et la cohérence de
chaque élément listé ci-dessous et comparer le classement au prototype ; vérifier qu'un
visiteur non connecté ne peut pas l'ouvrir.

**Acceptance Scenarios**:

1. **Given** un rapport, **When** le demandeur l'ouvre, **Then** il voit : le nombre de
   points par priorité et par type, une carte de la commune avec les points et les voies
   très fréquentées par les bus, une liste classée par rang, des filtres par priorité, par
   type de point et par type de route.
2. **Given** un point sélectionné, **When** sa fiche s'affiche, **Then** elle indique :
   rang, priorité, score, type de point, nom, **direction** (arrêts), voie, **type de route et gestionnaire**,
   passages de bus par jour et en pointe, lignes, pente, revêtement, ensoleillement, îlot de
   chaleur, âge estimé de l'enrobé le cas échéant, photo de rue récente le cas échéant, et
   la liste des facteurs qui ont pesé sur son score avec leur valeur.
3. **Given** le type de route d'un point, **When** les deux référentiels disponibles
   divergent ou sont muets, **Then** la fiche l'indique (« indéterminé » ou « à vérifier »)
   plutôt que d'afficher une valeur incertaine comme sûre.
4. **Given** un rapport, **When** le demandeur lit la section méthode, **Then** il y trouve
   la version de la méthode, chaque facteur et son effet, les règles de priorité et les
   **limites connues**, dont celles de l'ensoleillement et des îlots de chaleur (à
   approfondir en 004).
5. **Given** un rapport, **When** le demandeur lit la section sources, **Then** chaque
   source figure avec sa licence, son lien et sa date d'extraction, et les résultats issus
   d'un modèle d'IA sont marqués « à confirmer » avec le modèle et la date.
6. **Given** un rapport, **When** le demandeur l'enregistre, **Then** il reste lisible hors
   connexion (fichier autonome), hormis le fond de carte.
7. **Given** un rapport, **When** il est ouvert sur un téléphone, **Then** il reste lisible
   et utilisable (terrain).
8. **Given** plusieurs quais portant le même nom d'arrêt (un par direction, parfois plusieurs
   dans une même direction), **When** le demandeur les voit dans la liste, la carte ou la
   fiche, **Then** chacun se distingue sans ambiguïté par sa **direction**, sa voie, ses
   lignes et l'identifiant IDFM du quai (exemple : « Paix - Verdun » à Courbevoie compte
   trois quais classés P1, P1 et P2).

---

### User Story 4 - Maîtriser les coûts et suivre le service (Priority: P2)

Le mainteneur connaît, pour chaque rapport, sa durée, son coût d'IA, les sources utilisées
et les éventuels avertissements ; le service ne dépasse jamais les plafonds fixés.

**Why this priority**: principes II et V ; nécessaire avant d'ouvrir le service, mais pas au
premier rapport de démonstration.

**Independent Test**: générer deux rapports et vérifier le journal de chacun ; forcer le
plafond de coût d'IA et vérifier que le rapport est produit sans les analyses restantes,
avec un avertissement.

**Acceptance Scenarios**:

1. **Given** un rapport terminé, **When** le mainteneur consulte son journal, **Then** il y
   trouve durée, nombre de points, nombre d'analyses d'IA, coût d'IA, sources et dates,
   avertissements.
2. **Given** le plafond de coût d'IA d'un rapport atteint, **When** la génération continue,
   **Then** les points restants sont marqués « âge de l'enrobé non évalué » et le rapport
   l'indique ; aucune dépense supplémentaire n'a lieu.
3. **Given** le budget global quotidien atteint, **When** une génération est demandée,
   **Then** elle est refusée avec un message explicite et le mainteneur est alerté.
4. **Given** une génération en échec, **When** le mainteneur consulte le journal, **Then** il
   trouve l'étape et la source en cause ; le demandeur a reçu un message compréhensible sans
   détail technique.

---

### Edge Cases

- **Code postal à cheval sur deux départements** ou commune nouvelle : la liste proposée est
  celle du référentiel officiel au moment de la demande.
- **Commune sans ligne de bus** ou sans aucun point : le rapport est produit et l'indique
  (« aucun point à relever ») plutôt que d'échouer.
- **Paris (75)** : 20 arrondissements, codes postaux par arrondissement ; Paris est traitée
  **arrondissement par arrondissement** (décision du plan, research R6) : un rapport par
  arrondissement.
- **Source indisponible** pendant la génération : nouvelle tentative ; si une source
  optionnelle (photos de rue, îlots de chaleur) reste indisponible, le rapport est produit
  avec le facteur marqué « non évalué » et un avertissement ; si une source indispensable
  (arrêts et offre de bus, voirie) est indisponible, la génération échoue proprement.
- **Données sources mises à jour** entre deux demandes : l'empreinte change, un nouveau
  rapport est produit ; l'ancien reste accessible par son lien.
- **Deux demandes simultanées** pour la même commune : une seule génération (US2-6).
- **Réponse d'IA invalide ou hors bornes** : ignorée, point marqué « non évalué ».
- **Adresse e-mail erronée** : aucun lien n'arrive ; le demandeur peut corriger et
  redemander, dans la limite fixée (US2-8).
- **Lien de connexion ouvert sur un autre appareil** que celui de la demande : accepté (usage
  terrain : demande sur ordinateur, lecture sur téléphone).
- **Rapport téléchargé puis transmis** à un tiers : le fichier autonome reste lisible par ce
  tiers ; le rapport rappelle qu'il est destiné à son demandeur et à la collectivité
  concernée.
- **Demande d'effacement de compte** : l'adresse et l'historique des demandes sont
  supprimés ; les rapports, qui ne contiennent aucune donnée personnelle, restent en cache.
- **Point situé sur une limite communale** : rattaché à la commune où il se trouve ; les
  points hors commune ne sont pas inclus.
- **Génération trop longue** : interrompue au-delà d'une durée maximale, en échec explicite ;
  les autres communes du lot ne sont pas affectées.
- **Lot vide** au déclenchement : aucun traitement, arrêt immédiat, coût négligeable.
- **File plus longue qu'un lot** : les demandes restantes passent au lot suivant, dans
  l'ordre d'arrivée ; la position et l'heure estimée affichées sont mises à jour.
- **Budget quotidien d'IA** : s'il est **déjà épuisé au moment de la demande**, la demande est
  refusée avec un message explicite (US4-3) ; s'il est **insuffisant pour tout un lot**, les
  communes qui le dépasseraient restent en file pour le lendemain et le demandeur en est
  informé.
- **Coût mensuel** : le franchissement du seuil d'alerte mensuel (5 €) prévient le mainteneur
  mais ne bloque rien (FR-029).
- **Un déclenchement démarre alors que le lot précédent n'est pas fini** : il ne traite que
  les demandes non prises en charge ; une même demande n'est jamais traitée deux fois.

## Requirements *(mandatory)*

### Functional Requirements

**Saisie et validation**

- **FR-001**: Le service DOIT accepter un code postal et refuser, sans appel externe, toute
  saisie qui n'est pas composée de 5 chiffres.
- **FR-002**: Le service DOIT refuser les codes postaux hors des départements
  d'Île-de-France (75, 77, 78, 91, 92, 93, 94, 95) et les codes inexistants dans le
  référentiel officiel des communes.
- **FR-003**: Le service DOIT proposer toutes les communes d'Île-de-France couvertes par le
  code postal et exiger le choix d'une commune lorsqu'il y en a plusieurs.
- **FR-004**: Le service DOIT exiger une preuve antibot valide, à usage unique et à durée de
  vie limitée, avant d'envoyer un lien de connexion et avant de lancer une génération ; la protection DOIT fonctionner sans service
  tiers, sans cookie de suivi et rester accessible (clavier, lecteur d'écran).
- **FR-005**: Le service DOIT limiter les générations par compte (5 par jour) et au total
  (50 par jour), et les demandes de lien de connexion par adresse (3 par heure) et par
  origine (10 par heure) ; les consultations de rapports existants par un utilisateur
  connecté ne sont pas limitées par ces quotas.
- **FR-006**: Le service DOIT authentifier le demandeur avant toute génération et toute
  consultation de rapport, par lien de connexion envoyé à son adresse e-mail : sans mot de
  passe, à usage unique, valable 15 minutes ; la session ouverte expire après 7 jours.
  Toute adresse e-mail valide peut créer un compte (constitution, principe I : point
  d'appel authentifié).
- **FR-006b**: Les réponses aux demandes de lien de connexion NE DOIVENT pas révéler si une
  adresse possède déjà un compte.

**Génération**

- **FR-007**: Le service DOIT générer le rapport d'une commune sans intervention manuelle, en
  trois étapes (acquisition, calcul, rapport) dont l'avancement est visible du demandeur.
- **FR-007a**: Une demande sans rapport en cache DOIT être placée dans une file d'attente
  persistante ; les demandes sont traitées **par lots**, déclenchés à intervalle régulier
  (toutes les 15 minutes), dans l'ordre d'arrivée, à raison de 10 communes par lot au plus.
  Aucune ressource de calcul ne tourne entre deux lots (principe II).
- **FR-007b**: Au sein d'un lot, les données communes à toute la région DOIVENT être
  acquises et préparées une seule fois, puis partagées entre les communes du lot.
- **FR-007c**: Le demandeur DOIT voir sa position dans la file et une heure estimée de
  traitement, et DOIT être prévenu par e-mail de la fin (succès ou échec) de sa demande.
- **FR-007d**: Une demande DOIT être prise en charge par un seul lot ; un échec sur une
  commune NE DOIT pas interrompre les autres communes du lot.
- **FR-008**: Le service DOIT renvoyer un rapport existant, sans recalcul, lorsque la
  commune, les versions courantes des sources, la version de méthode et le modèle d'IA sont
  identiques et que le rapport date de moins de 30 jours. Les versions courantes des sources
  sont mises à jour au plus une fois par jour.
- **FR-009**: Le service NE DOIT conserver qu'une demande par commune et par empreinte, en
  file ou en cours ; les demandes concurrentes y sont rattachées.
- **FR-010**: Le service DOIT identifier les points d'une commune : arrêts de bus desservis,
  carrefours à feux et giratoires traversés par au moins une ligne de bus.
- **FR-011**: Le service DOIT calculer pour chaque point les facteurs de la méthode du
  prototype (charge, sollicitation, site, ensoleillement, îlot de chaleur, âge de l'enrobé
  pour les P1) et un score déterministe versionné ; même entrée ⇒ même classement.
- **FR-012**: Le service DOIT attribuer les priorités par rang : P1 = 20 % des points les
  plus exposés, P2 = 40 % suivants, P3 = le reste. Pour ordonner les relevés, les P1 sont
  découpés par rang final (après l'âge de l'enrobé) en trois tiers **P1a**, **P1b**, **P1c**,
  affichés et filtrables (méthode 1.1, demande du mainteneur du 2026-09-29 : 31 P1 sur 154 à
  Courbevoie n'aidaient pas à prioriser).
- **FR-013**: Le service DOIT déterminer pour chaque point le **type de route**
  (autoroute, nationale, départementale, communale, voie privée, indéterminé) et le
  **gestionnaire** correspondant, en croisant deux référentiels ouverts et en signalant les
  divergences. En 002, ce type est affiché et filtrable mais n'entre pas dans le score.
- **FR-014**: Le service DOIT estimer par analyse d'images historiques par IA la période de
  la dernière réfection de l'enrobé, **uniquement pour les points P1** (priorités établies
  et **figées** avant ce facteur) ; le résultat est marqué « à confirmer » avec
  le modèle et la date, ne modifie le score et le rang que dans les bornes de la méthode
  (×0,85 à ×1,05) et **à l'intérieur des P1** : il ne fait jamais changer un point de
  priorité (principe V ; écart assumé avec le prototype), est mis en cache avec le rapport et respecte le plafond de coût (FR-024). Le
  modèle d'IA DOIT être hébergé en France (constitution, principe III).
- **FR-015**: Le service DOIT rattacher à chaque point, quand elle existe, la photo de rue
  ouverte la plus récente à moins de 30 m, avec sa date et un lien.
- **FR-016**: Chaque point DOIT avoir un identifiant stable d'une génération à l'autre, pour
  y rattacher plus tard des relevés terrain (principe VI).
- **FR-017**: La génération d'une commune DOIT être interrompue au-delà de 30 minutes et
  marquée en échec ; un lot entier DOIT s'arrêter au-delà de 3 heures, les communes non
  traitées retournant en tête de file.

**Rapport**

- **FR-018**: Le rapport DOIT contenir : synthèse chiffrée, carte, liste classée filtrable
  (priorité, type de point, type de route), fiche par point (FR-011, FR-013, FR-015),
  méthode avec version et limites, sources avec licence, lien et date d'extraction.
- **FR-019**: Le rapport DOIT distinguer les valeurs mesurées, estimées et issues d'IA, et
  marquer « non évalué » tout facteur indisponible.
- **FR-020**: Le rapport DOIT être un document autonome, consultable hors connexion à
  l'exception du fond de carte, lisible sur ordinateur et sur téléphone.
- **FR-021**: Seuls les utilisateurs connectés DOIVENT pouvoir consulter un rapport ; tout
  utilisateur connecté peut consulter tout rapport déjà généré (le cache est partagé). Il
  n'existe pas de liste publique des rapports ; chaque utilisateur voit la liste de ses
  propres demandes.
- **FR-030**: Chaque arrêt DOIT être désigné, dans la liste, la carte et la fiche, par son
  nom, sa **direction** (terminus desservis depuis ce quai), sa voie, ses lignes et
  l'identifiant IDFM du quai. Une direction inconnue est affichée « direction non
  déterminée », jamais devinée. La direction est descriptive : elle ne modifie ni le score ni
  le classement.
- **FR-022**: Le rapport DOIT rappeler qu'il classe des points à relever en priorité et ne
  mesure pas l'état réel de la chaussée.

**Exploitation**

- **FR-023**: Chaque génération DOIT produire un journal : durée par étape, nombre de
  points, sources et dates, nombre et coût des analyses d'IA, avertissements, erreurs.
- **FR-024**: Le coût d'IA DOIT être plafonné à 2 € par rapport et à 5 € par jour pour
  l'ensemble du service ; les plafonds atteints produisent un rapport partiel signalé ou un
  refus, jamais une dépense supplémentaire.
- **FR-029**: Le mainteneur DOIT être alerté, une seule fois par mois civil, dès que le coût
  du service atteint **5 €** sur le mois : d'une part le coût d'IA cumulé suivi par le
  service, d'autre part la facturation totale du projet chez l'hébergeur (calcul, base,
  stockage, e-mail, IA). Cette alerte ne bloque rien.
- **FR-025**: Les messages d'erreur montrés au demandeur NE DOIVENT contenir aucun détail
  technique ; le détail est dans le journal.
- **FR-026**: Le service NE DOIT conserver comme données personnelles que l'adresse e-mail
  du compte, la date de dernière connexion et la liste des demandes de l'utilisateur ; les
  identifiants d'origine utilisés pour la limitation de débit sont conservés 24 h au plus.
- **FR-027**: Un compte inactif depuis 12 mois DOIT être supprimé automatiquement ; un
  utilisateur DOIT pouvoir supprimer son compte lui-même. L'information RGPD (finalité,
  durée, droits) DOIT être présentée avant la création du compte.
- **FR-028**: Les e-mails de connexion et de notification DOIVENT être envoyés par un service hébergé dans
  l'Union européenne et ne contenir que le strict nécessaire (lien, délai de validité, nom de la commune).

### Key Entities

- **Commune** : code INSEE, nom, département, contour ; obtenue à partir d'un code postal.
- **Compte** : adresse e-mail, date de création, date de dernière connexion.
- **Lien de connexion** : compte visé, date d'émission, date d'expiration, utilisé ou non.
- **Demande de génération** : comptes demandeurs, commune, état (en file, acquisition,
  calcul, rapport, terminée, en échec), position, heure estimée, horodatages, empreinte, lot.
- **Lot** : déclenchement, demandes prises en charge, données régionales partagées, durée,
  coût, résultat par commune.
- **Empreinte de rapport** : commune + version de méthode + versions des sources ; clé du
  cache.
- **Point** : identifiant stable, type (arrêt, carrefour à feux, giratoire), nom, position,
  voie, type de route, gestionnaire, facteurs, score, rang, priorité.
- **Facteur** : nom, valeur, effet sur le score, provenance (mesuré, estimé, IA), statut
  (évalué, non évalué, à confirmer).
- **Source** : nom, licence, lien, date d'extraction.
- **Rapport** : empreinte, version de méthode, points, synthèse, méthode, sources, limites.
- **Journal de génération** : durées, coûts, avertissements, erreurs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un demandeur obtient le rapport d'une commune déjà générée en moins de
  10 secondes après validation du formulaire.
- **SC-002**: En fonctionnement normal (file de moins de 10 demandes), 95 % des rapports de
  communes de moins de 100 000 habitants sont disponibles moins de 45 minutes après la
  demande, attente du lot comprise.
- **SC-002b**: Le temps de calcul d'un lot de 10 communes est inférieur d'au moins 30 % à la
  somme des temps de calcul de ces communes traitées séparément.
- **SC-002c**: 100 % des demandeurs dont la demande aboutit ou échoue reçoivent un e-mail.
- **SC-003**: Le rapport de Courbevoie retrouve au moins 80 % des P1 du prototype parmi ses
  P1, tout écart restant étant expliqué par une différence de source ou de méthode
  documentée.
  *Décision du mainteneur (2026-09-28) : résultat mesuré de 74 % (23/31) **accepté** ; les
  8 écarts sont expliqués dans `tests/non_regression/test_courbevoie.py` (surtout
  l'ensoleillement, refondu en 004). Le test verrouille ce niveau et exige une explication
  pour tout nouvel écart.*
- **SC-004**: Deux générations de la même commune avec les mêmes sources et la même méthode
  produisent un classement identique à 100 %.
- **SC-005**: 100 % des points d'un rapport ont un type de route renseigné ou explicitement
  marqué « indéterminé » ; sur un échantillon de 50 points vérifiés à la main, au moins 90 %
  des types renseignés sont exacts.
- **SC-006**: 100 % des soumissions sans preuve antibot valide, hors Île-de-France ou au-delà
  des quotas sont refusées sans génération lancée ni e-mail envoyé.
- **SC-007**: Le coût d'IA ne dépasse jamais 2 € par rapport ni 5 € par jour.
- **SC-008**: Aucun coût d'hébergement de calcul n'est facturé entre deux lots ; un
  déclenchement sur file vide dure moins de 30 secondes (principe II).
- **SC-009**: Un demandeur qui découvre le service lance sa première génération en moins de
  3 minutes, connexion par e-mail comprise, sans aide.
- **SC-010**: 100 % des tentatives de génération ou de consultation sans session valide sont
  refusées.
- **SC-011**: 95 % des e-mails de connexion arrivent en moins de 1 minute.
- **SC-012**: Sur un échantillon de 30 points P1 dont la date de réfection est connue, l'IA
  donne la bonne période dans au moins 70 % des cas et ne fait jamais changer un point de
  priorité à elle seule.
- **SC-013**: Le mainteneur reçoit l'alerte mensuelle au plus tard le jour où le coût du mois
  franchit 5 €, et jamais plus d'une alerte de chaque type par mois.

## Assumptions

- Référentiel des codes postaux et communes : API Géo officielle (données ouvertes).
- Méthode de départ = méthode du prototype v2, versionnée « 1.0 » ; ses limites
  (ensoleillement, îlots de chaleur) sont affichées et traitées en 004.
- Type de route : classement administratif de la base topographique nationale, recoupé avec
  la référence de route du référentiel collaboratif ; le gestionnaire se déduit du
  classement (État ou concessionnaire, département, commune, privé).
- Intervalle entre lots (15 min), taille de lot (10 communes), durée maximale d'un lot
  (3 h) : valeurs de départ réglables ; l'intervalle pourra être allongé si la demande reste
  faible.
- Quotas, plafonds et durées (5/jour/compte, 50/jour, 3 et 10 liens/h, 15 min, 7 jours,
  12 mois, 2 €, 5 €/jour, 5 €/mois d'alerte, 30 jours de validité d'un rapport, 30 min,
  30 m) sont des valeurs de départ réglables sans modification de la spec.
- Inscription ouverte à toute adresse e-mail ; une liste d'adresses ou de domaines autorisés
  pourra être ajoutée si des abus sont constatés (hors périmètre 002).
- L'estimation de l'âge de l'enrobé reprend la lecture du prototype : comparaison
  d'orthophotos de plusieurs années sur l'emprise du point.
- Échelle d'une commune seulement ; départements en 005.
- La carte du rapport est dessinée à partir des données (sans fond de carte) : le rapport est
  entièrement lisible hors connexion (plan, research R8).
- La constitution impose antibot, quotas, hébergement en France et journal des coûts.
