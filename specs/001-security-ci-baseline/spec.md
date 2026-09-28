# Feature Specification: Socle de sécurité CI

**Feature Branch**: `001-security-ci-baseline`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Socle sécurité CI : la sécurité est la priorité absolue ; check des vulnérabilités, analyse du code, avec GitHub Actions (principe I de la constitution). Inclut la recherche de secrets, l'analyse des images et de l'infrastructure, le SBOM, SECURITY.md et CODEOWNERS."

## User Scenarios & Testing *(mandatory)*

Acteurs :

- **Mainteneur** : humain responsable du dépôt, seul habilité à fusionner (principe IX).
- **Contributeur** : humain ou agent IA qui propose des changements par PR depuis une
  branche dédiée.
- **Signaleur externe** : personne qui découvre une vulnérabilité et veut la signaler.

### User Story 1 - Une PR dangereuse ne peut pas être fusionnée (Priority: P1)

Un contributeur ouvre une PR. Avant toute fusion, des contrôles automatiques analysent le code
modifié, les dépendances ajoutées et la présence de secrets. Si une faille critique ou élevée,
une dépendance vulnérable ou un secret est détecté, la PR est marquée en échec et le mainteneur
ne peut pas la fusionner tant que le problème n'est pas corrigé ou formellement accepté.

**Why this priority**: c'est le cœur du principe I ; sans ce blocage, toutes les autres
mesures ne sont que des alertes ignorables.

**Independent Test**: ouvrir trois PR de test contenant respectivement un motif de code
vulnérable connu, une dépendance avec vulnérabilité critique publiée et un faux secret au
format reconnu ; vérifier que chacune est bloquée avec un message qui désigne le problème.

**Acceptance Scenarios**:

1. **Given** une PR qui introduit un motif de code classé critique ou élevé, **When** les
   contrôles s'exécutent, **Then** la PR est en échec et le problème est localisé (fichier,
   ligne, règle).
2. **Given** une PR qui ajoute une dépendance affectée par une vulnérabilité critique ou
   élevée connue, **When** les contrôles s'exécutent, **Then** la PR est en échec et
   l'identifiant de la vulnérabilité est affiché.
3. **Given** une PR contenant un secret (clé API, jeton, mot de passe), **When** les
   contrôles s'exécutent, **Then** la PR est en échec et le secret n'est pas réaffiché en
   clair dans les résultats.
4. **Given** une PR sans problème, **When** les contrôles s'exécutent, **Then** ils sont tous
   au vert et la PR est fusionnable par le mainteneur.
5. **Given** un contrôle de sécurité requis qui n'a pas pu s'exécuter (erreur, annulation),
   **When** le mainteneur tente de fusionner, **Then** la fusion est refusée : l'absence de
   résultat vaut échec.

---

### User Story 2 - Les vulnérabilités découvertes après coup sont signalées et corrigées (Priority: P2)

Une vulnérabilité est publiée sur une dépendance déjà présente dans `main`. Le mainteneur
en est averti sans avoir à ouvrir de PR, et une proposition de mise à jour corrective est
créée automatiquement sous forme de PR, soumise aux mêmes contrôles et fusionnée par un
humain.

**Why this priority**: la majorité des vulnérabilités apparaissent dans du code déjà
fusionné ; le blocage des PR (P1) ne les voit pas.

**Independent Test**: sur une branche de test, déclarer une version de dépendance connue pour
être vulnérable, lancer l'analyse planifiée et vérifier la création de l'alerte et de la PR de
correction.

**Acceptance Scenarios**:

1. **Given** une vulnérabilité publiée sur une dépendance de `main`, **When** l'analyse
   périodique s'exécute, **Then** une alerte est visible dans le tableau de sécurité du dépôt
   avec sa gravité.
2. **Given** qu'une version corrigée existe, **When** l'alerte est créée, **Then** une PR de
   mise à jour est ouverte automatiquement et n'est jamais fusionnée automatiquement.
3. **Given** des dépendances non vulnérables mais obsolètes, **When** la période de mise à
   jour arrive, **Then** des PR de mise à jour groupées sont proposées sans submerger le
   mainteneur.

---

### User Story 3 - Chaque livraison est inventoriée et ses artefacts analysés (Priority: P3)

Lorsqu'une version est livrée, un inventaire complet des composants (SBOM) est produit et
attaché à la version. Les images de conteneur et les fichiers d'infrastructure déclarés
dans le dépôt sont analysés avant livraison ; une vulnérabilité critique ou élevée bloque la
livraison.

**Why this priority**: il n'existe encore ni image ni infrastructure ; ce contrôle doit être
prêt avant le premier déploiement mais n'a pas d'effet immédiat.

**Independent Test**: créer une version de test et vérifier la présence du SBOM attaché ;
ajouter un fichier d'infrastructure volontairement mal configuré et vérifier le blocage.

**Acceptance Scenarios**:

1. **Given** une nouvelle version publiée, **When** le processus de livraison s'exécute,
   **Then** un SBOM dans un format standard est attaché à la version.
2. **Given** une image de conteneur ou un fichier d'infrastructure contenant une faille
   critique ou élevée, **When** les contrôles s'exécutent sur la PR ou la livraison,
   **Then** la PR ou la livraison est bloquée.
3. **Given** un dépôt sans image ni infrastructure, **When** les contrôles s'exécutent,
   **Then** ils réussissent sans erreur (absence d'objet à analyser ≠ échec).

---

### User Story 4 - Signaler une faille et exiger une revue humaine sur les zones sensibles (Priority: P3)

Un signaleur externe trouve dans le dépôt une procédure claire pour signaler une faille en
privé. Toute modification des zones sensibles (automatisations CI, constitution, méthode de
score, fichiers de configuration des agents) exige la revue du mainteneur désigné.

**Why this priority**: exigé par le principe I (SECURITY.md) et le principe IX (CODEOWNERS),
mais peu coûteux et sans dépendance.

**Independent Test**: vérifier la présence de la politique de sécurité et du canal privé ;
ouvrir une PR modifiant un fichier de CI et vérifier que la revue du mainteneur est demandée
automatiquement.

**Acceptance Scenarios**:

1. **Given** un visiteur du dépôt, **When** il consulte l'onglet sécurité, **Then** il trouve
   la politique de signalement, le canal privé et le délai de première réponse.
2. **Given** une PR qui modifie un fichier d'une zone sensible, **When** elle est ouverte ou
   mise à jour, **Then** un commentaire unique de la PR liste les fichiers sensibles modifiés
   et rappelle la relecture obligatoire ; si l'auteur n'est pas le propriétaire désigné,
   celui-ci est en plus demandé automatiquement en revue.

---

### Edge Cases

- **Faux positif** : un contrôle bloque à tort. Le mainteneur peut enregistrer une exception
  documentée (raison, date d'expiration, responsable) ; à expiration, le blocage revient.
- **Aucune correction disponible** pour une vulnérabilité critique : exception temporaire
  obligatoire avec plan d'atténuation, sinon blocage maintenu.
- **Secret déjà poussé** dans l'historique : l'alerte déclenche la révocation du secret
  (le retirer du code ne suffit pas) et une entrée `LESSON-LEARNED.md`.
- **Workflow modifié par une PR** pour se désactiver ou élargir ses permissions : sur une PR,
  GitHub exécute la version des workflows **contenue dans la PR** ; une PR peut donc
  neutraliser un contrôle en gardant son nom. Parade : toute PR touchant une zone sensible
  (dont `.github/`) est signalée de façon visible et exige la relecture humaine du diff de
  ces fichiers avant fusion ; aucune automatisation ne remplace cette relecture.
- **PR ouverte depuis un fork** : les contrôles s'exécutent sans accès aux secrets du dépôt.
- **Action tierce compromise ou retaguée** : les actions référencées sont épinglées par
  empreinte de commit, donc un nouveau tag malveillant n'est pas exécuté.
- **Service d'analyse indisponible** : le contrôle est en échec (pas de fusion « par défaut »).

## Requirements *(mandatory)*

### Functional Requirements

**Contrôles sur chaque PR et chaque push**

- **FR-001**: Le système DOIT analyser statiquement le code de chaque PR et de chaque push sur
  `main` et signaler les failles avec leur gravité et leur localisation.
- **FR-002**: Le système DOIT analyser les dépendances ajoutées ou modifiées par une PR et
  signaler celles affectées par une vulnérabilité connue.
- **FR-003**: Le système DOIT rechercher les secrets dans les changements proposés et dans
  l'historique du dépôt, et bloquer un push contenant un secret reconnu.
- **FR-004**: Le système DOIT analyser les images de conteneur et les fichiers
  d'infrastructure présents dans le dépôt, et réussir proprement s'il n'y en a pas.
- **FR-005**: Toute détection de gravité critique ou élevée DOIT mettre la PR en échec ; les
  gravités moyenne et faible DOIVENT être signalées sans bloquer. Exception : les règles de
  durcissement des automatisations (FR-014) bloquent quelle que soit leur gravité.
- **FR-006**: Les contrôles FR-001 à FR-004 DOIVENT être déclarés comme contrôles requis de
  la branche `main` : aucune fusion possible sans résultat vert, y compris pour le mainteneur.

**Surveillance continue**

- **FR-007**: Le système DOIT réanalyser `main` au moins une fois par semaine, indépendamment
  de toute PR, pour détecter les vulnérabilités publiées après fusion.
- **FR-008**: Le système DOIT proposer automatiquement des PR de mise à jour de sécurité pour
  les dépendances vulnérables, et des PR de mise à jour groupées au moins mensuelles pour les
  dépendances et les actions CI obsolètes.
- **FR-009**: Aucune PR automatique (mise à jour de dépendances ou autre bot) ne DOIT être
  fusionnée automatiquement (principe IX).

**Livraison**

- **FR-010**: Chaque version livrée DOIT être accompagnée d'un SBOM dans un format standard
  reconnu, attaché à la version.
- **FR-011**: La livraison DOIT être bloquée si l'analyse de ses artefacts relève une
  vulnérabilité critique ou élevée non couverte par une exception valide.

**Durcissement des automatisations**

- **FR-012**: Chaque automatisation CI DOIT déclarer explicitement des permissions minimales ;
  aucune ne DOIT hériter des permissions par défaut.
- **FR-013**: Chaque action tierce DOIT être référencée par empreinte de commit complète, et
  les mises à jour de ces références DOIVENT passer par FR-008.
- **FR-014**: Un contrôle DOIT échouer si une automatisation ne respecte pas FR-012 ou FR-013.

**Exceptions, gouvernance et signalement**

- **FR-015**: Une exception à un blocage DOIT être enregistrée dans le dépôt avec
  l'identifiant du problème, la raison, le responsable et une date d'expiration de 90 jours
  au plus ; une exception expirée DOIT redevenir bloquante. Pour les outils dont
  l'ignorance est déclarée dans le dépôt (analyse des dépendances, vulnérabilités, secrets),
  ce retour au blocage est automatique ; pour les alertes d'analyse de code ignorées dans
  l'interface, il est vérifié par une revue mensuelle du mainteneur.
- **FR-016**: Le dépôt DOIT publier une politique de sécurité indiquant les versions
  supportées, le canal de signalement privé et un délai de première réponse de 7 jours.
- **FR-017**: Le dépôt DOIT désigner un propriétaire obligatoire pour les zones sensibles :
  automatisations CI, constitution, configuration des agents, méthode de score, politique de
  sécurité.
- **FR-018**: Les résultats de tous les contrôles DOIVENT être centralisés dans le tableau de
  sécurité du dépôt, consultable par le mainteneur.

### Key Entities

- **Constat de sécurité** : problème détecté ; attributs : source du contrôle, gravité,
  localisation, identifiant (règle ou vulnérabilité), statut (ouvert, corrigé, excepté).
- **Exception** : acceptation temporaire d'un constat ; attributs : constat visé, raison,
  responsable, date de création, date d'expiration.
- **Contrôle requis** : vérification dont le résultat vert conditionne la fusion sur `main`.
- **SBOM** : inventaire des composants d'une version livrée, rattaché à cette version.
- **Zone sensible** : ensemble de chemins du dépôt soumis à revue obligatoire du propriétaire.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des PR de test piégées (code vulnérable, dépendance vulnérable, secret,
  infrastructure mal configurée) sont bloquées avant fusion.
- **SC-002**: 0 PR fusionnée sur `main` sans que tous les contrôles requis soient au vert,
  vérifiable dans l'historique du dépôt.
- **SC-003**: Les contrôles d'une PR typique rendent leur verdict en moins de 10 minutes.
- **SC-004**: Une vulnérabilité publiée sur une dépendance de `main` est signalée au
  mainteneur en moins de 7 jours.
- **SC-005**: 100 % des versions livrées ont un SBOM attaché.
- **SC-006**: 100 % des automatisations CI ont des permissions explicites et des actions
  tierces épinglées (contrôle FR-014 au vert).
- **SC-007**: Aucune exception active n'a dépassé sa date d'expiration.
- **SC-008**: Le coût récurrent de ce socle est nul tant que le dépôt reste public
  (principe II).

## Assumptions

- Le dépôt `aboigues/bitumap` est **public** : les fonctions de sécurité de la plateforme
  (analyse de code, recherche de secrets, revue des dépendances) sont gratuites. Un passage
  en privé imposerait une licence payante et une révision de SC-008.
- La constitution impose GitHub Actions et nomme CodeQL pour l'analyse de code ; le choix des
  autres outils relève de `/speckit-plan`.
- La recherche de secrets et la protection au push sont déjà activées côté dépôt ; les mises à
  jour de sécurité automatiques ne le sont pas encore.
- Le dépôt ne contient encore ni code applicatif, ni image, ni infrastructure : les contrôles
  doivent fonctionner à vide puis s'appliquer automatiquement quand ces éléments arrivent.
- Le mainteneur unique est `aboigues` ; il reçoit les alertes par les notifications GitHub.
- Délais de correction par défaut : critique 7 jours, élevée 30 jours, moyenne au fil de
  l'eau.
- La configuration du ruleset de `main` (ajout des contrôles requis) est une action humaine
  (principe IX) ; la fonctionnalité fournit la liste exacte des contrôles à exiger.
- Dépendance : le ruleset `ProtectTheMain` doit cibler la branche par défaut (correction en
  attente côté mainteneur).
