# Feature Specification: Projection de l'orniérage été par été

**Feature Branch**: `007-projection-ete`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "007 — Projection (issue #20) : en tant qu'utilisateur, je souhaite un rapport complémentaire sur l'évolution des ornières dans le temps en fonction de la fréquentation et de plusieurs projections des températures (scénario 1 : tendances météo neutres, scénario 2 : chaud, scénario 3 : très très chaud). Précisions du mainteneur (2026-09-29) : indice relatif dans un premier temps ; scénarios très concrets pour aider les équipes à intervenir rapidement : été 2027, 2028, etc."

## Contexte

Le rapport de 002 classe les points d'une commune **aujourd'hui**. Les équipes veulent
savoir **lesquels traiter avant quel été**, selon que l'été prochain sera moyen, chaud ou très
chaud. L'orniérage constaté à « Paix - Verdun » (Courbevoie) après les canicules de l'été 2026,
sur un enrobé sain en octobre 2025, montre qu'un seul été très chaud suffit.

Cette fonctionnalité produit un **rapport complémentaire** par commune : pour chaque point,
l'évolution d'un **indice de potentiel d'orniérage** été après été (2027, 2028…), selon trois
scénarios d'été tirés d'étés réellement observés, et la fréquentation des bus.

L'indice est **relatif** : il compare les points et les étés entre eux, il ne donne pas une
profondeur d'ornière en millimètres. Le passage en millimètres demandera des mesures répétées
sur le terrain (relevés de 003) pour calibrer un modèle ; il est hors périmètre.

Hors périmètre : profondeur en millimètres, projections climatiques à long terme (2050,
2100), planification budgétaire des travaux, refonte du facteur chaleur (004).

## User Scenarios & Testing *(mandatory)*

Acteur : **agent de collectivité ou de bureau d'études**, connecté, qui prépare le programme
d'entretien de la voirie empruntée par les bus.

### User Story 1 - Savoir quels points traiter avant l'été prochain (Priority: P1)

Depuis le rapport d'une commune, l'agent ouvre la projection. Pour chaque scénario (été
moyen, été chaud, été très chaud), il voit la liste des points qui atteignent le seuil
d'intervention avant l'été 2027, puis avant 2028, et ainsi de suite, avec pour chacun
l'été où le seuil est atteint.

**Why this priority**: c'est la décision que les équipes doivent prendre : quoi traiter,
avant quel été.

**Independent Test**: sur Courbevoie, ouvrir la projection : pour chaque scénario, lire la
liste des points à traiter avant l'été 2027 ; dans le scénario très chaud, « Paix - Verdun »
(quai 23742) y figure.

**Acceptance Scenarios**:

1. **Given** le rapport d'une commune, **When** l'agent ouvre la projection, **Then** il voit,
   pour chaque scénario, les points qui atteignent le seuil d'intervention, groupés par été
   (avant 2027, avant 2028, …).
2. **Given** un point, **When** l'agent consulte sa projection, **Then** il voit, pour chaque
   scénario, l'été où le seuil est atteint (ou « pas avant 20XX » au-delà de l'horizon).
3. **Given** les trois scénarios, **When** l'agent les compare, **Then** un point n'atteint
   jamais le seuil plus tard dans un scénario plus chaud.

---

### User Story 2 - Comprendre les scénarios et l'évolution d'un point (Priority: P1)

L'agent lit ce que recouvre chaque scénario (quel été observé il reproduit, combien de jours
de forte chaleur) et, pour un point, la courbe de son indice été après été dans les trois
scénarios, avec ce qui la fait monter (fréquentation, exposition à la chaleur, âge de
l'enrobé s'il est connu).

**Why this priority**: une projection qu'on ne comprend pas ne sera pas utilisée pour
engager des travaux (constitution, principe IV).

**Independent Test**: ouvrir la fiche projection de « Paix - Verdun » : trois courbes, le
seuil, l'été de franchissement par scénario et l'explication de chaque facteur.

**Acceptance Scenarios**:

1. **Given** la projection, **When** l'agent lit la description des scénarios, **Then** il
   voit pour chacun l'été observé de référence et son nombre de jours de forte chaleur.
2. **Given** la fiche d'un point, **When** l'agent l'ouvre, **Then** il voit l'évolution de
   l'indice dans les trois scénarios, le seuil d'intervention et les facteurs qui le font
   évoluer.
3. **Given** un point dont l'année de la dernière réfection est connue (IA « à confirmer »
   ou relevé de 003), **When** la projection est calculée, **Then** l'indice en tient
   compte, et la fiche indique la source de cette année.

---

### User Story 3 - Tester une hypothèse de fréquentation (Priority: P2)

L'agent indique une évolution de la fréquentation des bus (stable, ou +x % par an, par
exemple après une restructuration du réseau) et voit la projection recalculée.

**Why this priority**: la fréquentation est l'autre moteur de l'orniérage ; aucune projection
publique n'existe, l'agent doit pouvoir poser son hypothèse.

**Independent Test**: sur Courbevoie, passer de « stable » à « +5 % par an » : des points
atteignent le seuil plus tôt, aucun plus tard.

**Acceptance Scenarios**:

1. **Given** la projection, **When** l'agent choisit « +5 % par an », **Then** la projection
   est recalculée et l'hypothèse est indiquée en tête du rapport.
2. **Given** une hypothèse de fréquentation, **When** l'agent exporte, **Then** l'hypothèse
   figure dans l'export.

---

### User Story 4 - Exporter la projection (Priority: P2)

L'agent exporte la projection dans un format de tableur : un enregistrement par point et par
scénario, avec l'été de franchissement du seuil et l'indice par été.

**Why this priority**: les programmes d'entretien sont construits dans les outils des services
techniques.

**Independent Test**: exporter la projection de Courbevoie et l'ouvrir dans un tableur.

**Acceptance Scenarios**:

1. **Given** une projection, **When** l'agent l'exporte, **Then** le fichier contient chaque
   point, chaque scénario, l'indice par été et l'été de franchissement du seuil.

---

### Edge Cases

- Point non évalué pour la chaleur (donnée absente) : projection faite avec une exposition
  neutre, marquée « chaleur non évaluée ».
- Année de réfection inconnue : l'indice part de l'état actuel sans ancienneté, signalé
  « âge de l'enrobé inconnu ».
- Point refait après la date du rapport (relevé de 003 indiquant une réfection récente) :
  l'indice repart de zéro à la date de réfection.
- Horizon dépassé : « pas avant 20XX » (fin de l'horizon), jamais une date extrapolée.
- Données météo d'un été récent pas encore publiées : le scénario reste fondé sur l'été
  observé de référence ; la date des données est indiquée.

## Requirements *(mandatory)*

### Functional Requirements

**Scénarios et horizon**

- **FR-001**: La projection DOIT couvrir les étés suivant la date du rapport, un par un, sur un
  horizon de 5 étés (par exemple 2027 à 2031).
- **FR-002**: Trois scénarios DOIVENT être proposés, chacun reproduisant chaque été un été
  réellement observé dans la région : **été moyen** (moyenne des étés récents), **été chaud**
  (type 2019 ou 2022), **été très chaud** (type 2003 ou 2026). La description de chaque
  scénario indique l'été de référence et son nombre de jours de forte chaleur.
- **FR-003**: Les données climatiques observées DOIVENT venir d'une source publique sous
  licence ouverte et être partagées avec 004 (une seule acquisition).

**Indice et seuil**

- **FR-004**: Pour chaque point, un **score projeté** (indice de potentiel d'orniérage) DOIT
  être calculé été après été, sur l'échelle du score du rapport : il part du score actuel du
  point (issu de la méthode en vigueur) et augmente avec la sollicitation par les bus
  (fréquentation) et l'exposition à la chaleur de chaque été ; il tient compte de l'âge de
  l'enrobé quand il est connu.
- **FR-005**: L'indice DOIT être présenté comme **relatif** (« potentiel », jamais en
  millimètres), avec la mention qu'il ne mesure pas l'état réel de la chaussée.
- **FR-006**: Le **seuil d'intervention** DOIT être un score de **95/100**, sur l'échelle du
  score du rapport en vigueur (100 = point le plus exposé de la commune à la date du rapport ;
  le score projeté peut dépasser 100). Valeur empirique fixée par le mainteneur le
  2026-09-29, modifiable par configuration et affichée dans le rapport ; elle sera affinée
  avec les relevés terrain (003) et les photos, chaque changement étant tracé dans le journal
  des changements de méthode.
- **FR-007**: Pour chaque point et chaque scénario, la projection DOIT indiquer l'été où le
  seuil est atteint, ou « pas avant » la fin de l'horizon.
- **FR-008**: Un scénario plus chaud NE DOIT jamais faire atteindre le seuil plus tard ; une
  fréquentation plus forte non plus.

**Fréquentation**

- **FR-009**: L'agent DOIT pouvoir choisir l'évolution de la fréquentation : stable (par
  défaut) ou un pourcentage annuel entre -5 % et +10 % ; l'hypothèse est affichée et
  exportée.

**Restitution**

- **FR-010**: La projection DOIT être un rapport complémentaire, accessible depuis le rapport
  de la commune, avec la liste des points à traiter par été et par scénario, une fiche par
  point (courbes, seuil, facteurs) et la description des scénarios.
- **FR-011**: La projection DOIT être exportable dans un format de tableur (un enregistrement
  par point et par scénario).
- **FR-012**: La projection DOIT être déterministe et reproductible : même rapport, mêmes
  données climatiques, même hypothèse ⇒ même projection ; elle porte sa propre version de
  méthode, décrite dans le journal des changements de méthode (constitution, principe IV).

### Key Entities *(include if feature involves data)*

- **Scénario d'été** : nom (moyen, chaud, très chaud), été observé de référence, nombre de
  jours de forte chaleur, source et date des données.
- **Projection** : rapport de commune d'origine, hypothèse de fréquentation, horizon,
  version de méthode, date.
- **Trajectoire d'un point** : pour un point et un scénario, indice par été, été de
  franchissement du seuil, facteurs (fréquentation, chaleur, âge de l'enrobé et sa source).
- **Seuil d'intervention** : score projeté qui déclenche « à traiter » (95/100 au départ,
  empirique), sa date de fixation et sa justification ; versionné avec la méthode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Pour une commune comme Courbevoie, l'agent obtient en moins de 2 minutes, par
  scénario, la liste des points à traiter avant l'été prochain.
- **SC-002**: Dans le scénario très chaud, « Paix - Verdun » (quai 23742), orniéré après l'été
  2026, atteint le seuil dès le premier été de l'horizon.
- **SC-003**: Pour 100 % des points, l'été de franchissement du seuil n'est jamais plus tardif
  dans un scénario plus chaud ou avec une fréquentation plus forte.
- **SC-004**: Deux calculs d'une même projection avec les mêmes données et la même hypothèse
  donnent un résultat identique pour 100 % des points.
- **SC-005**: 100 % des fiches point présentent l'indice comme relatif, sans valeur en
  millimètres.
- **SC-006**: Sur les points relevés dans 003 à deux dates différentes, les points dont
  l'orniérage s'aggrave sont plus souvent ceux que la projection place en tête (vérification
  à la première campagne de relevés répétés).

## Assumptions

- La projection réutilise le rapport en vigueur de la commune (002) : points, fréquentation,
  exposition à la chaleur et à l'ensoleillement ; elle bénéficiera de la méthode v2 (004)
  quand celle-ci sera en service.
- Les étés de référence sont des étés observés dans la région (station de référence
  représentative de l'agglomération) ; la variation locale de la chaleur entre points vient
  du rapport (îlots de chaleur, ensoleillement), pas de la station.
- L'âge de l'enrobé vient de l'IA (« à confirmer », points prioritaires seulement) ou des
  relevés de 003 (année de réfection) ; à défaut, il est inconnu et signalé.
- Aucune projection publique de fréquentation n'existe ; l'hypothèse est celle de l'agent.
- L'horizon de 5 étés est une valeur de départ, modifiable par configuration.
- Le score de départ est celui du rapport, tel que la méthode en vigueur le calcule ; il
  pourra être complété par l'analyse des photos (orthophotos, photos de rue, photos des
  relevés de 003) dans une version ultérieure.
- Le seuil de 95/100 étant relatif au point le plus exposé de chaque commune, il ne compare
  pas deux communes entre elles ; c'est une limite affichée dans le rapport.
- L'authentification et les comptes de 002 sont réutilisés.
