# Feature Specification: Parcours de surveillance

**Feature Branch**: `006-parcours-surveillance`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "006 — Parcours de surveillance (issue #21) : en tant qu'utilisateur, je souhaite un export GPX détaillé avec un itinéraire en boucle depuis une adresse, pour générer un parcours de surveillance des ornières par niveau. Modes : voiture et à pied (vélo abandonné par le mainteneur le 2026-09-29)."

## Contexte

Le rapport d'une commune classe ses points en niveaux (Critique, Sérieux, Important, À
surveiller, Supportable) et les place sur une carte. Pour aller les voir, l'agent doit
aujourd'hui composer lui-même sa tournée. Cette fonctionnalité produit, à partir d'une
adresse de départ (le centre technique, par exemple) et des niveaux choisis, un **itinéraire
en boucle** qui passe par tous les points retenus et revient au départ, en voiture ou à pied,
avec un fichier GPX à charger dans un GPS ou une application de navigation.

Hors périmètre : parcours à vélo (écarté par le mainteneur), navigation guidée pas à pas dans
le service, parcours sur plusieurs communes, suivi en temps réel de l'agent.

## User Scenarios & Testing *(mandatory)*

Acteur : **agent de terrain**, utilisateur connecté qui consulte le rapport d'une commune
(002) et prépare une tournée de surveillance ou de relevés (003).

### User Story 1 - Obtenir une boucle depuis une adresse (Priority: P1)

Depuis le rapport d'une commune, l'agent indique une adresse de départ, choisit les niveaux à
visiter (par exemple Critique et Sérieux), le mode (voiture ou à pied) et la durée maximale de
sa tournée (par exemple 3 heures). Il obtient un itinéraire en boucle qui part de l'adresse,
visite les points **dans l'ordre de leur rang** (les plus critiques d'abord), s'arrête quand
la durée serait dépassée et revient au départ, avec la distance, la durée estimée et la liste
des points laissés pour une prochaine tournée.

**Why this priority**: c'est le besoin exprimé ; sans la boucle, pas de parcours.

**Independent Test**: sur le rapport de Courbevoie, depuis l'hôtel de ville, niveaux Critique
et Sérieux (21 points), en voiture, durée maximale 3 heures : obtenir une boucle qui visite les
points dans l'ordre du rang, tient dans les 3 heures retour compris, et liste les points non
visités.

**Acceptance Scenarios**:

1. **Given** un rapport de commune et une adresse valide dans la commune ou à proximité,
   **When** l'agent choisit des niveaux, un mode et une durée maximale puis valide, **Then**
   il obtient une boucle qui commence et finit à l'adresse, visite les points dans l'ordre de
   leur rang, une seule fois chacun, et dont la durée totale (trajets, arrêts et retour) ne
   dépasse pas la durée choisie.
2. **Given** des points qui ne tiennent pas dans la durée, **When** la boucle est calculée,
   **Then** ils sont listés comme « non visités, pour une prochaine tournée », avec leur rang.
3. **Given** une boucle calculée, **When** l'agent la consulte, **Then** il voit la distance
   totale, la durée estimée, le nombre de points et l'ordre de visite.
4. **Given** une adresse introuvable ou ambiguë, **When** l'agent valide, **Then** il lui est
   proposé de choisir parmi les adresses possibles, ou un message clair s'affiche.
5. **Given** le mode « à pied », **When** la boucle est calculée, **Then** elle emprunte des
   cheminements piétons et sa durée est une durée de marche.

---

### User Story 2 - Télécharger le parcours en GPX (Priority: P1)

L'agent télécharge le parcours au format GPX : le tracé de la boucle et un point de passage
par point du rapport, avec sa désignation (nom, direction, voie, lignes), son niveau, son rang
et son identifiant, dans l'ordre de visite. Il le charge dans son GPS ou son application de
navigation.

**Why this priority**: le GPX est le livrable demandé ; il rend le parcours utilisable hors du
service.

**Independent Test**: télécharger le GPX de la story 1 et l'ouvrir dans deux applications de
navigation courantes : le tracé et les points visités apparaissent, nommés et dans l'ordre
du rang.

**Acceptance Scenarios**:

1. **Given** une boucle calculée, **When** l'agent télécharge le GPX, **Then** le fichier
   contient le tracé complet et un point de passage par point retenu, dans l'ordre de visite.
2. **Given** un point de passage, **When** il est affiché dans l'application, **Then** son nom
   donne l'ordre, le niveau et la désignation (par exemple « 3 · Critique · Paix - Verdun ·
   vers Argenteuil… »).
3. **Given** le GPX, **When** il est ouvert, **Then** il ne contient aucune donnée
   personnelle (ni adresse e-mail, ni compte) ; l'adresse de départ n'y figure que sous forme
   de point de départ.

---

### User Story 3 - Voir le parcours et la feuille de route dans le rapport (Priority: P2)

L'agent voit la boucle sur la carte du rapport et une feuille de route imprimable : liste des
points dans l'ordre de visite, avec niveau, désignation et distance cumulée.

**Why this priority**: utile pour préparer et partager la tournée ; le GPX suffit pour la
réaliser.

**Independent Test**: après la story 1, la carte montre la boucle et la feuille de route
s'imprime sur une page A4 pour une vingtaine de points.

**Acceptance Scenarios**:

1. **Given** une boucle calculée, **When** l'agent revient au rapport, **Then** la carte montre
   la boucle et numérote les points dans l'ordre de visite.
2. **Given** la feuille de route, **When** l'agent l'imprime, **Then** chaque point y figure
   avec son ordre, son niveau, sa désignation et la distance cumulée.

---

### User Story 4 - Ne visiter que les points pas encore relevés (Priority: P3)

Quand les relevés terrain (003) existent, l'agent peut exclure les points déjà relevés
depuis moins d'un nombre de jours qu'il choisit, pour ne visiter que ce qui reste à faire.

**Why this priority**: gain de temps réel, mais dépend de 003.

**Independent Test**: avec des relevés récents sur 5 des 21 points, l'option « exclure les
points relevés depuis moins de 30 jours » ne retient que les 16 autres comme candidats à la
boucle.

**Acceptance Scenarios**:

1. **Given** des points relevés récemment, **When** l'agent active l'exclusion, **Then** ces
   points ne sont pas dans la boucle et le résumé indique combien ont été exclus.

---

### Edge Cases

- Aucun point dans les niveaux choisis : message clair, aucun parcours.
- Durée trop courte pour visiter même le premier point (aller, arrêt et retour) : message
  clair indiquant la durée minimale nécessaire.
- Tous les points tiennent dans la durée : la boucle les visite tous et indique le temps
  restant.
- Point inaccessible dans le mode choisi (par exemple arrêt dans un site propre bus, ou point
  à pied séparé par une voie rapide) : le passage se fait au point accessible le plus proche,
  signalé dans la feuille de route.
- Adresse de départ hors de la commune : acceptée si elle reste raisonnablement proche
  (moins de 20 km) ; au-delà, refus explicite.
- Service de calcul d'itinéraire indisponible : message clair ; aucun GPX partiel n'est fourni.
- Rapport régénéré entre deux téléchargements : le parcours indique la date du rapport dont
  il est issu.

## Requirements *(mandatory)*

### Functional Requirements

**Calcul du parcours**

- **FR-001**: Un utilisateur connecté DOIT pouvoir demander un parcours depuis le rapport d'une
  commune, en indiquant une adresse de départ, un ou plusieurs niveaux et un mode.
- **FR-002**: Les modes proposés DOIVENT être « voiture » et « à pied » ; le vélo n'est pas
  proposé.
- **FR-003**: L'adresse de départ DOIT être reconnue parmi les adresses officielles ; en cas
  d'ambiguïté, l'utilisateur choisit parmi les propositions.
- **FR-004**: Le parcours DOIT être une boucle : départ et arrivée à l'adresse, passage une
  seule fois par chaque point retenu, sur le réseau praticable dans le mode choisi.
- **FR-005**: L'ordre de visite DOIT suivre le **rang** des points (les plus critiques
  d'abord), sans réordonnancement pour raccourcir le trajet ; chaque trajet entre deux points
  consécutifs est le plus rapide dans le mode choisi (décision du mainteneur du 2026-09-29).
- **FR-006**: L'agent DOIT fixer une **durée maximale de tournée** (3 heures par défaut, de
  30 minutes à 8 heures), qui comprend les trajets, un temps d'arrêt par point (5 minutes par
  défaut, modifiable) et le retour au départ. Les points sont pris dans l'ordre du rang : un
  point qui ferait dépasser la durée est laissé de côté et le suivant est essayé (décision du
  mainteneur du 2026-09-29).
- **FR-006b**: Les points laissés de côté DOIVENT être listés, avec leur rang et leur niveau,
  comme « non visités, pour une prochaine tournée ».
- **FR-007**: Le parcours DOIT indiquer la distance totale, la durée estimée (trajets, arrêts,
  retour), le nombre de points visités et non visités, et la date du rapport utilisé.

**Export**

- **FR-008**: Le parcours DOIT être téléchargeable au format GPX, lisible par les GPS et
  applications de navigation courants : tracé complet et un point de passage par point,
  nommé (ordre, niveau, désignation) et décrit (rang, identifiant, lien vers la fiche).
- **FR-009**: Une feuille de route imprimable DOIT lister les points dans l'ordre de visite,
  avec niveau, désignation et distance cumulée.
- ~~**FR-010**: La carte du rapport DOIT pouvoir afficher la boucle et l'ordre de visite.~~
  *Abandonnée (décision du mainteneur, 2026-10-05)* : la boucle se suit dans le GPX
  (FR-008), qui contient le tracé complet et les points numérotés ; le rapport stocké ne
  garde ni le contour ni les voies nécessaires à un nouveau dessin.

**Relevés (dépend de 003)**

- **FR-011**: Quand 003 est en service, l'utilisateur DOIT pouvoir exclure les points relevés
  depuis moins d'un nombre de jours choisi.

**Données personnelles et sécurité**

- **FR-012**: L'adresse de départ NE DOIT être conservée que le temps du calcul et du
  téléchargement (au plus 24 h) ; le GPX et la feuille de route ne contiennent aucune donnée
  de compte.
- **FR-013**: Les demandes de parcours DOIVENT être limitées (20 par compte et par jour), pour
  protéger les services tiers de calcul d'itinéraire et d'adresse et le coût du service
  (constitution, principe I).
- **FR-014**: Seuls des services de calcul d'itinéraire et d'adresse publics, hébergés en
  France et sous licence ouverte DOIVENT être utilisés ; leurs sources sont citées dans le
  GPX et la feuille de route (constitution, principe III).

### Key Entities *(include if feature involves data)*

- **Demande de parcours** : commune, rapport utilisé, adresse de départ, niveaux, mode, durée
  maximale, temps d'arrêt par point, option d'exclusion des points relevés ; éphémère.
- **Parcours** : ordre de visite (ordre du rang), tracé, distance, durée, points visités, non
  visités et exclus, date du rapport, sources.
- **Point de passage** : point du rapport dans le parcours : ordre, niveau, désignation,
  position de passage, identifiant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Pour une commune comme Courbevoie et 20 à 30 points, un parcours est proposé en
  moins de 30 secondes.
- **SC-002**: Le GPX s'ouvre sans erreur dans au moins deux applications de navigation
  courantes et un GPS de randonnée, avec 100 % des points nommés et dans l'ordre.
- **SC-003**: Les points sont visités dans l'ordre de leur rang dans 100 % des parcours, et la
  durée estimée ne dépasse jamais la durée maximale choisie.
- **SC-007**: Sur 3 tournées réelles, la durée effective (trajets et arrêts) reste dans un
  écart de ±20 % de la durée estimée.
- **SC-004**: 100 % des points des niveaux choisis figurent dans le parcours, ou sont listés
  comme non visités (durée) ou inaccessibles dans le mode choisi.
- **SC-005**: Un agent prépare sa tournée (adresse, niveaux, mode, téléchargement) en moins de
  2 minutes.
- **SC-006**: Aucune adresse de départ n'est conservée au-delà de 24 heures.

## Assumptions

- Le parcours se calcule sur les points du rapport en vigueur de la commune (002) ; un
  parcours ne couvre qu'une commune.
- Le point de passage d'un arrêt est la position du quai (002, direction et identifiant) ; en
  voiture, le parcours n'impose pas le sens de circulation du bus devant le quai.
- Les services publics de calcul d'itinéraire et d'adresse (voiture et piéton, adresses
  officielles) sont utilisés pour chaque trajet entre deux points ; l'ordre de visite, lui,
  est imposé par le rang.
- L'ordre du rang allonge volontairement le trajet par rapport à une tournée optimisée : les
  points les plus critiques sont vus même si la tournée est interrompue.
- L'authentification et les comptes de 002 sont réutilisés.
- Le rapport HTML restant consultable hors ligne, le calcul du parcours demande une connexion ;
  le GPX téléchargé, lui, s'utilise hors ligne.
