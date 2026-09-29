# Feature Specification: Relevés terrain

**Feature Branch**: `003-terrain-releves`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "003 Relevés terrain : annotations et photos par commune et par point (feuille de route du README ; constitution, principe VI)."

## Contexte

Le rapport de 002 est un **premier tri de bureau** : il classe les points où aller relever en
priorité, sans mesurer l'état réel de la chaussée. Cette fonctionnalité permet aux équipes
d'aller sur place et de **consigner ce qu'elles constatent** sur chaque point : présence et
gravité de l'orniérage, profondeur mesurée, observations, date de la dernière réfection si
elle est connue, photos.

Ces relevés forment la couche « constaté », distincte du calcul « estimé » (constitution,
principe VI) : ils ne modifient jamais le score ni le classement, mais ils s'affichent à côté,
dans le rapport. Ils servent aussi :

- à constituer l'échantillon de points à date de réfection connue qui permet de choisir le
  modèle d'IA (002, T073, SC-012) ;
- à calibrer plus tard la projection de l'orniérage en millimètres (fonctionnalité 007), grâce
  à des mesures répétées dans le temps ;
- à vérifier la méthode : un point classé Critique est-il réellement orniéré ?

Hors périmètre : modification du score par les relevés (le calcul reste déterministe,
principe IV), relevés sur un emplacement qui n'est pas un point du rapport, parcours de
surveillance (006), projection (007).

## Clarifications

### Session 2026-09-29

- Q: Sous quelle forme afficher l'auteur d'un relevé aux autres utilisateurs connectés ? → A: pseudonyme stable et domaine de l'adresse (« agent 7F3A · ville-courbevoie.fr ») ; adresse complète visible par le seul mainteneur.
- Q: Comment définir les niveaux d'orniérage constaté pour que deux agents classent de la même façon ? → A: repères chiffrés affichés à la saisie (léger < 10 mm, marqué 10–20 mm, grave > 20 mm, profondeur maximale à la règle) ; une mesure qui contredit le niveau déclenche un avertissement, sans bloquer.
- Q: Combien de temps conserver les photos des relevés ? → A: sans limite de durée, comme le relevé (sauf retrait).

## User Scenarios & Testing *(mandatory)*

Acteurs :

- **Agent de terrain** : agent de collectivité ou de bureau d'études, connecté, qui se rend
  sur les points d'un rapport, le plus souvent avec un téléphone.
- **Lecteur** : utilisateur connecté qui consulte le rapport d'une commune.
- **Mainteneur** : responsable du service ; traite les demandes de retrait et surveille les
  volumes.

### User Story 1 - Consigner un relevé sur un point, depuis le terrain (Priority: P1)

Sur place, l'agent ouvre le rapport de la commune sur son téléphone, sélectionne le point
devant lequel il se trouve, puis saisit ce qu'il constate : orniérage absent, léger, marqué
ou grave ; profondeur maximale mesurée s'il a pu la mesurer ; observation libre ; année de la
dernière réfection s'il la connaît ; une ou plusieurs photos. Il valide : le relevé est
enregistré avec la date, l'heure et son auteur.

**Why this priority**: c'est la raison d'être de la fonctionnalité ; sans saisie, pas de
couche « constaté ».

**Independent Test**: sur le rapport de Courbevoie, saisir un relevé complet (niveau, mesure,
observation, année de réfection, deux photos) sur le point « Paix - Verdun » (quai 23742),
puis le retrouver dans le rapport.

**Acceptance Scenarios**:

1. **Given** un agent connecté qui consulte le rapport d'une commune, **When** il choisit un
   point et saisit un niveau d'orniérage puis valide, **Then** le relevé est enregistré avec
   la date, l'heure, l'auteur et l'identifiant du point, et une confirmation s'affiche.
2. **Given** un relevé en cours de saisie, **When** l'agent ajoute des photos prises avec son
   téléphone, **Then** elles sont rattachées au relevé, leur position est gardée, et les
   métadonnées permettant de localiser ou d'identifier l'appareil sont retirées.
3. **Given** un réseau mobile absent au moment de valider, **When** l'agent valide,
   **Then** le relevé et ses photos sont conservés sur le téléphone et envoyés dès que le
   réseau revient, sans ressaisie ; l'agent voit qu'ils sont en attente d'envoi.
4. **Given** une saisie incomplète (aucun niveau d'orniérage), **When** l'agent valide,
   **Then** la validation est refusée avec un message clair : le niveau est le seul champ
   obligatoire.
5. **Given** un niveau « léger » et une profondeur saisie de 25 mm, **When** l'agent valide,
   **Then** un avertissement signale que 25 mm correspond à « grave » ; l'agent peut
   corriger ou confirmer son choix.

---

### User Story 2 - Voir le constaté à côté de l'estimé dans le rapport (Priority: P1)

Le lecteur ouvre le rapport d'une commune. Sur chaque point relevé, la fiche montre une
section « Constaté » distincte de « Estimé » : dernier relevé (niveau, mesure, observation,
année de réfection, date, auteur, et ses photos s'il en est l'auteur) et historique des
relevés précédents. La liste et
la carte signalent les points relevés et permettent de filtrer (relevés, non relevés, par
niveau constaté). La synthèse compte les points relevés et croise niveau estimé et niveau
constaté.

**Why this priority**: sans consultation, les relevés restent invisibles pour les autres
agents et pour la vérification de la méthode.

**Independent Test**: après le relevé de la story 1, ouvrir le rapport de Courbevoie depuis un
autre appareil : la fiche de « Paix - Verdun » montre le constaté, la carte le signale, et le
score et le rang du point sont inchangés.

**Acceptance Scenarios**:

1. **Given** un point relevé, **When** le lecteur ouvre sa fiche, **Then** il voit le dernier
   relevé dans une section « Constaté », séparée de l'estimé, avec la date et l'auteur.
2. **Given** un relevé avec photos saisi par un autre agent, **When** le lecteur ouvre la
   fiche, **Then** il voit le relevé et le nombre de photos, mais pas les photos ; l'auteur
   du relevé, lui, voit ses photos.
3. **Given** un rapport déjà produit, **When** un nouveau relevé est enregistré, **Then** il
   apparaît dans le rapport sans le régénérer, et le score, le rang et le niveau du point
   restent identiques.
4. **Given** le rapport d'une commune, **When** le lecteur filtre sur « relevés, orniérage
   marqué ou grave », **Then** seuls ces points s'affichent dans la liste et sur la carte.
5. **Given** plusieurs relevés d'un même point, **When** le lecteur ouvre l'historique,
   **Then** il voit tous les relevés, du plus récent au plus ancien.
6. **Given** la synthèse du rapport, **When** des points ont été relevés, **Then** elle
   indique le nombre de points relevés et, par niveau estimé (Critique … Supportable), la
   répartition des niveaux constatés.

---

### User Story 3 - Corriger ou retirer son relevé (Priority: P2)

L'auteur d'un relevé se rend compte d'une erreur (mauvais point, mauvais niveau, photo
inadaptée). Il corrige : une nouvelle version remplace l'affichage, l'ancienne reste dans
l'historique. Il peut aussi retirer un relevé ou une photo : ils disparaissent de l'affichage,
mais la trace du retrait (qui, quand) est conservée.

**Why this priority**: les erreurs de saisie sont fréquentes sur le terrain ; sans
correction, la couche « constaté » perd sa fiabilité. Elle peut attendre la première
version si la saisie est soignée.

**Independent Test**: corriger le niveau d'un relevé puis retirer une photo : l'affichage
montre la version corrigée, l'historique garde les deux versions et la trace du retrait.

**Acceptance Scenarios**:

1. **Given** un relevé de l'agent, **When** il le corrige, **Then** la version corrigée
   s'affiche et la précédente reste consultable dans l'historique, datée.
2. **Given** un relevé d'un autre agent, **When** un agent tente de le corriger ou de le
   retirer, **Then** l'action est refusée.
3. **Given** une photo retirée, **When** un lecteur consulte le point, **Then** la photo
   n'est plus visible et l'historique indique qu'une photo a été retirée, par qui et quand.

---

### User Story 4 - Exporter les relevés d'une commune (Priority: P2)

Un agent exporte les relevés d'une commune dans un format lisible par un tableur et par un
logiciel de cartographie : un enregistrement par relevé (point, position, niveau estimé,
niveau constaté, mesure, année de réfection, observation, date, nombre de photos ; liens vers
les photos pour les seuls relevés dont il est l'auteur).

**Why this priority**: les services techniques travaillent dans leurs propres outils ;
l'export sert aussi à constituer l'échantillon de T073 (points à date de réfection connue) et
les séries de mesures de 007.

**Independent Test**: exporter les relevés de Courbevoie et ouvrir le fichier dans un
tableur et dans un logiciel de cartographie : chaque relevé est présent et positionné.

**Acceptance Scenarios**:

1. **Given** une commune avec des relevés, **When** l'agent demande l'export, **Then** il
   obtient un fichier tableur et un fichier cartographique contenant chaque relevé visible.
2. **Given** un export, **When** on le compare au rapport, **Then** le niveau estimé de
   chaque point est celui du rapport en vigueur à la date de l'export.
3. **Given** des points dont l'année de réfection est renseignée, **When** l'agent exporte
   avec l'option « échantillon de réfection », **Then** il obtient la liste au format
   attendu par l'évaluation du modèle d'IA (002, T073).

---

### User Story 5 - Traiter une demande de retrait (Priority: P3)

Une personne signale qu'une photo la montre, ou montre sa plaque d'immatriculation (les
photos ne sont visibles que par leur auteur et le mainteneur, mais elles restent stockées).
Le mainteneur retire la photo de l'affichage et de l'export, avec une trace du retrait, sans
supprimer le reste du relevé.

**Why this priority**: obligation RGPD ; rare si les photos sont prises correctement, mais
elle doit exister dès la mise en service.

**Independent Test**: signaler une photo, la retirer en tant que mainteneur, vérifier
qu'elle n'apparaît plus ni dans le rapport ni dans l'export.

**Acceptance Scenarios**:

1. **Given** une photo signalée, **When** le mainteneur la retire, **Then** elle
   n'apparaît plus nulle part et la trace du retrait est conservée, sans la photo.
2. **Given** un compte supprimé (002, FR-027), **When** on consulte ses relevés, **Then**
   ils restent visibles sans aucune donnée permettant d'identifier leur auteur.

---

### Edge Cases

- Point qui disparaît d'une nouvelle génération du rapport (arrêt supprimé par IDFM) : ses
  relevés sont conservés et restent consultables dans l'historique de la commune, signalés
  « point absent du rapport en vigueur ».
- Relevé saisi hors de la commune ou loin du point (position de l'appareil à plus de 100 m) :
  enregistré, mais signalé « position éloignée du point » ; aucune obligation de géolocaliser.
- Deux agents relèvent le même point le même jour : les deux relevés sont conservés et
  affichés, sans fusion.
- Photo trop lourde, format non image, ou nombre de photos dépassé : refus explicite avant
  envoi, le reste du relevé est conservé.
- Envoi en attente (hors réseau) puis session expirée : le relevé reste sur le téléphone et
  part après reconnexion ; il n'est jamais perdu sans avertissement.
- Commune dont le rapport n'a jamais été généré : pas de relevé possible (les relevés se
  rattachent aux points d'un rapport).
- Quota de relevés ou de photos atteint : refus explicite ; le relevé saisi reste en
  brouillon sur le téléphone.

## Requirements *(mandatory)*

### Functional Requirements

**Saisie**

- **FR-001**: Un utilisateur connecté DOIT pouvoir saisir un relevé sur tout point du rapport
  d'une commune, depuis un téléphone comme depuis un ordinateur.
- **FR-002**: Un relevé DOIT comporter : le point (identifiant stable, 002 FR-016), la date et
  l'heure, l'auteur et un **niveau d'orniérage constaté** parmi « absent », « léger »,
  « marqué », « grave » ; il PEUT comporter une profondeur maximale mesurée (en
  millimètres, avec l'instrument utilisé), une observation libre (1 000 caractères au plus),
  l'année de la dernière réfection et sa source (« constatée », « services techniques »,
  « estimée par l'agent »), et des photos.
- **FR-003**: Un relevé DOIT accepter au plus 5 photos de 10 Mo chacune, dans des formats
  d'image courants de téléphone ; la position de prise de vue est conservée, toute autre
  métadonnée d'identification (appareil, auteur, etc.) est retirée.
- **FR-004**: Une saisie validée sans réseau DOIT être conservée sur l'appareil et envoyée
  automatiquement au retour du réseau, avec un état visible « en attente d'envoi ».
- **FR-005**: Un relevé DOIT être refusé sans niveau d'orniérage, avec un message clair ; les
  autres champs sont facultatifs.
- **FR-005b**: La saisie DOIT afficher les repères de chaque niveau : **léger** < 10 mm,
  **marqué** de 10 à 20 mm, **grave** > 20 mm (profondeur maximale mesurée à la règle), pour
  un classement identique d'un agent à l'autre, même à l'œil. Quand une profondeur est saisie
  et ne correspond pas au niveau choisi, un avertissement s'affiche ; le relevé reste
  enregistrable avec le niveau choisi par l'agent.

**Consultation**

- **FR-006**: La fiche d'un point DOIT distinguer une section « Constaté » (relevés) de la
  section « Estimé » (calcul), et afficher le dernier relevé et l'historique complet.
- **FR-007**: Les relevés DOIVENT apparaître dans le rapport sans le régénérer ; ils ne
  modifient jamais le score, le rang ni le niveau estimé d'un point (constitution, principes
  IV et VI).
- **FR-008**: La liste et la carte DOIVENT signaler les points relevés et permettre de filtrer
  par présence de relevé et par niveau constaté.
- **FR-009**: La synthèse DOIT indiquer le nombre de points relevés et croiser niveau estimé
  et niveau constaté.
- **FR-010**: Tout utilisateur connecté DOIT pouvoir consulter les relevés de toutes les
  communes et en saisir sur tout point d'un rapport (savoir terrain partagé ; décision du
  mainteneur du 2026-09-29). L'auteur de chaque relevé est affiché sous la forme d'un
  **pseudonyme stable et du domaine de son adresse** (« agent 7F3A · ville-courbevoie.fr ») ;
  l'adresse complète n'est visible que par le mainteneur ; l'auteur voit ses propres
  relevés marqués « vous ». Un utilisateur non connecté n'a accès à aucun relevé.

**Historique et correction**

- **FR-011**: Un relevé enregistré n'est jamais écrasé : toute correction crée une nouvelle
  version datée ; l'historique des versions reste consultable.
- **FR-012**: Seul l'auteur d'un relevé PEUT le corriger ou le retirer ; le retrait masque le
  relevé ou la photo et conserve une trace (qui, quand).

**Export**

- **FR-013**: Les relevés visibles d'une commune DOIVENT être exportables dans un format de
  tableur et dans un format cartographique ouvert, un enregistrement par relevé, avec le
  niveau estimé du rapport en vigueur ; l'export ne contient de lien vers une photo que pour
  les relevés de l'utilisateur qui exporte (FR-015).
- **FR-014**: L'export DOIT proposer l'échantillon des points à année de réfection connue au
  format attendu par l'évaluation du modèle d'IA (002, T073).

**Données personnelles et sécurité**

- **FR-015**: Une photo NE DOIT être visible que par son auteur et par le mainteneur
  (RGPD : visages et plaques jamais diffusés ; décision du mainteneur du 2026-09-29). Les
  autres lecteurs voient le relevé sans ses photos, avec seulement leur nombre (« 2 photos,
  visibles par leur auteur »). Les photos sont conservées **sans limite de durée**, comme le
  relevé, sauf retrait (décision du mainteneur du 2026-09-29) ; justification RGPD : suivi de
  l'état de la voirie dans le temps (comparaison de constats sur plusieurs années), accès
  restreint à l'auteur et au mainteneur, retrait sur demande ; la page « Données
  personnelles » l'indique.
- **FR-016**: Le mainteneur DOIT pouvoir retirer une photo ou un relevé signalé ; la photo
  retirée n'apparaît plus ni dans le rapport ni dans l'export.
- **FR-017**: À la suppression d'un compte (002, FR-027), ses relevés DOIVENT rester
  consultables sans aucune donnée permettant d'identifier leur auteur ; ses photos ne sont
  plus visibles que par le mainteneur.
- **FR-018**: Les envois DOIVENT être limités en volume (quotas par compte : 200 relevés et
  1 000 photos par jour ; plafond global de stockage des photos), pour empêcher qu'un abus
  ne fasse exploser la facture (constitution, principe I).
- **FR-019**: Seuls les formats d'image attendus DOIVENT être acceptés, après vérification de
  leur contenu réel (pas seulement de leur extension).
- **FR-020**: Une photo NE DOIT jamais être accessible par une adresse publique permanente :
  seulement à un utilisateur autorisé, par un lien à durée limitée.

### Key Entities *(include if feature involves data)*

- **Relevé** : constat sur un point à une date ; identifiant, point (identifiant stable),
  commune, auteur (ou « auteur supprimé »), date et heure, niveau d'orniérage, profondeur
  mesurée et instrument, observation, année de réfection et sa source, position de saisie
  éventuelle, photos ; versions successives.
- **Version de relevé** : état d'un relevé à une date ; la plus récente est affichée, les
  autres restent dans l'historique.
- **Photo** : image rattachée à un relevé ; position de prise de vue, date, état (visible,
  retirée par l'auteur, retirée par le mainteneur) ; visible seulement par son auteur et
  par le mainteneur.
- **Retrait** : trace d'un masquage (relevé ou photo) : qui, quand, motif (erreur de
  l'auteur, demande RGPD).
- **Point** (existant, 002) : identifiant stable, commune, niveau estimé ; un point peut
  avoir zéro ou plusieurs relevés.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un agent saisit un relevé complet avec deux photos en moins de 2 minutes sur un
  téléphone, une fois devant le point.
- **SC-002**: Un relevé validé avec réseau est visible dans le rapport, par un autre
  utilisateur connecté, en moins d'une minute.
- **SC-003**: Aucun relevé ni photo validé n'est perdu, y compris après une saisie hors
  réseau (100 % des relevés en attente finissent envoyés ou signalés à l'agent).
- **SC-004**: Pour un même rapport, score, rang et niveau estimé de chaque point sont
  identiques avant et après l'ajout de relevés (100 % des points).
- **SC-005**: 100 % des corrections et retraits laissent une trace consultable ; aucun relevé
  n'est modifié sans nouvelle version.
- **SC-006**: Aucune photo servie ne contient de métadonnée d'identification de l'appareil
  ou de l'auteur (vérifié sur 100 % des photos d'un jeu de test).
- **SC-007**: L'export d'une commune de 150 points et 500 relevés s'ouvre sans retouche dans
  un tableur et dans un logiciel de cartographie.
- **SC-008**: Une demande de retrait RGPD est traitable par le mainteneur en moins de
  5 minutes, et la photo disparaît de l'affichage et de l'export immédiatement.
- **SC-009**: Aucune photo n'est visible par un utilisateur autre que son auteur et le
  mainteneur (vérifié sur tous les points d'accès : fiche, carte, historique, export).

## Assumptions

- Les relevés se rattachent uniquement aux points d'un rapport existant (identifiant stable,
  002 FR-016) ; un relevé sur un emplacement libre est hors périmètre.
- Le niveau constaté utilise quatre modalités simples (absent, léger, marqué, grave) plutôt
  qu'une norme d'auscultation : l'agent n'a pas toujours d'instrument ; la mesure en
  millimètres est facultative, avec l'instrument indiqué (règle et cale, jauge…).
- L'authentification et les comptes de 002 (lien de connexion par e-mail, session) sont
  réutilisés ; aucun nouveau mode de connexion.
- La saisie se fait dans un navigateur de téléphone récent, sans application à installer ;
  l'appareil photo du téléphone est utilisé directement.
- Les relevés et les photos sont conservés sans limite de durée (patrimoine de connaissance
  de la voirie, confirmé par le mainteneur le 2026-09-29), sauf retrait ; les données
  personnelles de l'auteur suivent 002 FR-026/FR-027 ; le plafond global de stockage (FR-018)
  borne le coût.
- Les relevés restent hébergés en France, dans le projet `BITUMAP` (constitution, principe
  III), sans transmission à un tiers.
- Les quotas de FR-018 sont des valeurs de départ, ajustables par configuration, comme ceux
  de 002.
