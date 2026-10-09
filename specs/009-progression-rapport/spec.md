# Spécification : progression en pourcentage de la génération d'un rapport

**Branche** : `009-progression-rapport`

**Créée le** : 2026-10-09

**Statut** : brouillon

**Origine** : issue #55 du mainteneur (2026-10-09), « Indiquer avec pourcentage la
progression du travail sur la génération du rapport », capture de la page de suivi de
Paris 17e à l'appui. Décision du mainteneur (2026-10-09) : passage par le flux Spec Kit,
livraison dans la version v0.1.3.

## Contexte

Pendant la génération d'un rapport, la page de suivi d'une demande n'affiche qu'une
phrase : « Génération en cours : étape **démarrage** ». Elle se recharge seule toutes les
30 secondes, mais rien n'indique où en est le travail ni s'il avance : sur la capture de
l'issue, l'étape affichée est « démarrage » alors que la génération était en cours depuis
plusieurs minutes.

Mesure réelle (Paris 17e, 270 points, version v0.1.2) : 8 min au total, dont lecture des
sources 95 s, analyses par l'IA 398 s (80 % du temps), calcul 11 s, mise en forme moins
d'une seconde. Les étapes affichées aujourd'hui ne correspondent pas à ce découpage :
l'étape « acquisition » laisse presque aussitôt la place à « calcul », pendant lequel les
sources sont lues et l'IA appelée au fil des points. Un pourcentage calculé par étape
resterait donc figé pendant presque toute la génération ; il doit avancer au fil du travail
réellement fait, en particulier point par point pendant les analyses par l'IA.

## Clarifications

### Session 2026-10-09

- Q : Faut-il afficher une estimation de la durée restante à côté du pourcentage ? → R :
  oui, dès qu'elle est fiable : une fois les analyses par l'IA commencées (leur rythme est
  alors connu), arrondie à la minute ; avant, le pourcentage seul.
- Q : Le pourcentage doit-il aussi apparaître dans la liste « Mes demandes » ? → R : oui,
  dans la colonne état (« en cours (42 %) ») ; la liste ne se recharge pas seule.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Voir le pourcentage avancer pendant la génération (priorité : P1)

Un agent a demandé le rapport de sa commune ; la génération a commencé. Sur la page de
suivi, il voit un pourcentage (et une barre) qui augmente régulièrement, accompagné d'une
phrase claire sur ce qui est en cours (lecture des données, analyse des photos aériennes,
calcul des priorités, mise en forme). Il n'a pas besoin de recharger la page.

**Pourquoi cette priorité** : c'est l'objet de l'issue ; sans indication d'avancement,
l'usager ne sait pas si le service travaille ou s'il est bloqué, et quitte ou relance.

**Test indépendant** : lancer la génération d'une commune ; pendant qu'elle se déroule,
relever le pourcentage affiché à intervalles réguliers ; il ne diminue jamais, augmente au
cours de chaque phase longue, et la page passe au lien vers le rapport à la fin.

**Scénarios d'acceptation** :

1. **Étant donné** une demande dont la génération vient de commencer, **quand**
   l'usager ouvre la page de suivi, **alors** il voit un pourcentage entre 0 et 100 %, une
   barre de progression et le libellé de la phase en cours, jamais « démarrage » au-delà
   des premières secondes.
2. **Étant donné** une génération dans sa phase d'analyse par l'IA (la plus longue),
   **quand** l'usager reste sur la page, **alors** le pourcentage affiché augmente au moins
   une fois par minute, sans action de sa part.
3. **Étant donné** deux relevés successifs de la page pendant la même génération, **quand**
   on les compare, **alors** le second pourcentage est supérieur ou égal au premier.
4. **Étant donné** une génération terminée, **quand** la page se met à jour, **alors**
   elle affiche le lien « Ouvrir le rapport » (comportement actuel) ; 100 % n'est jamais
   affiché tant que le rapport n'est pas disponible.
5. **Étant donné** une génération en échec (délai dépassé, erreur), **quand** la page se
   met à jour, **alors** elle affiche le message d'échec actuel, sans pourcentage figé.
6. **Étant donné** un lecteur d'écran, **quand** il parcourt la page, **alors** la
   progression est annoncée comme telle (valeur en pourcentage et phase en cours).

---

### Récit 2 — Savoir combien de temps il reste (priorité : P2)

Pendant les analyses par l'IA, l'agent voit, à côté du pourcentage, une estimation de la
durée restante arrondie à la minute (« environ 4 min restantes ») ; il décide d'attendre
ou de fermer la page en sachant qu'un courriel le préviendra.

**Pourquoi cette priorité** : utile pour décider d'attendre ; le pourcentage (P1) suffit
déjà à montrer que le service avance.

**Test indépendant** : pendant une génération réelle, relever l'estimation affichée et la
comparer à la durée restante effectivement constatée.

**Scénarios d'acceptation** :

1. **Étant donné** une génération qui n'a pas encore commencé ses analyses par l'IA,
   **quand** la page s'affiche, **alors** seul le pourcentage est affiché, sans durée
   restante.
2. **Étant donné** une génération dans sa phase d'analyse par l'IA, **quand** la page
   s'affiche, **alors** une durée restante arrondie à la minute est affichée (« environ
   N min restantes », « moins d'une minute » en dessous).
3. **Étant donné** une estimation affichée, **quand** la génération avance, **alors**
   l'estimation est recalculée à chaque mise à jour de la page.

---

### Cas limites

- Rapport déjà produit entre-temps par une autre demande de la même commune : la demande
  passe directement à « terminée » ; aucun pourcentage n'est affiché.
- Commune sans point à relever (aucune ligne de bus) : la génération se termine vite ; le
  pourcentage peut passer de sa valeur de départ au lien vers le rapport sans étapes
  intermédiaires visibles.
- Réponses de l'IA déjà en cache : les analyses sont presque instantanées ; le pourcentage
  avance vite pendant cette phase, sans jamais reculer ensuite.
- Plafond de coût de l'IA atteint en cours de génération : les points restants ne sont pas
  analysés ; le pourcentage poursuit sa progression (ces points comptent comme traités).
- Plusieurs usagers ont demandé la même commune : ils voient la même progression.
- Demande encore en file d'attente : la page garde son affichage actuel (position, heure
  estimée), sans pourcentage.
- Génération interrompue (délai maximal, arrêt du job) puis demande remise en file : le
  pourcentage disparaît au profit de l'affichage de la file ; à la reprise, il repart de
  sa valeur de départ.
- Page ouverte depuis un téléphone : la barre et le pourcentage restent lisibles à 360 px
  de large.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : Pendant la génération d'un rapport, la page de suivi DOIT afficher un
  pourcentage d'avancement (nombre entier de 0 à 100) et une barre de progression.
- **FR-002** : Le pourcentage DOIT refléter le travail réellement effectué, et non le seul
  nom de la phase : pendant les analyses par l'IA, il DOIT avancer au fil des points
  analysés.
- **FR-003** : Le pourcentage affiché pour une génération DOIT être croissant (jamais
  inférieur à une valeur affichée précédemment pour la même génération).
- **FR-004** : Le pourcentage NE DOIT PAS atteindre 100 % avant que le rapport soit
  disponible ; la fin de la génération est signalée par le lien vers le rapport.
- **FR-005** : La page DOIT afficher, avec le pourcentage, le libellé de la phase en cours,
  choisi parmi des libellés compréhensibles par un agent (par exemple « lecture des
  données », « analyse des photos aériennes », « calcul des priorités », « mise en forme du
  rapport ») ; le libellé « démarrage » ne DOIT apparaître que tant que la génération n'a
  pas réellement commencé.
- **FR-006** : La page DOIT se mettre à jour sans action de l'usager, avec au plus
  30 secondes de retard sur l'avancement enregistré (fréquence actuelle).
- **FR-007** : La progression DOIT être annoncée aux technologies d'assistance (valeur et
  phase).
- **FR-008** : Le suivi de la progression NE DOIT PAS ajouter de coût au repos : aucun
  composant ni traitement ne tourne en dehors des générations demandées (principe II), et
  l'enregistrement de l'avancement ne DOIT pas allonger sensiblement la génération.
- **FR-009** : L'avancement NE DOIT exposer aucune donnée autre que le pourcentage et la
  phase (ni identifiant de point, ni coût, ni détail d'erreur) ; il n'est visible que des
  usagers qui peuvent déjà voir le suivi de la demande.
- **FR-010** : Les états hors génération (en file, terminée, en échec, reportée) DOIVENT
  garder leur affichage actuel.
- **FR-011** : Une fois les analyses par l'IA commencées, la page de suivi DOIT afficher une
  estimation de la durée restante, arrondie à la minute (« moins d'une minute » en
  dessous) ; avant ce moment, aucune durée restante n'est affichée.
- **FR-012** : La liste « Mes demandes » DOIT afficher le pourcentage d'une demande en
  cours de génération dans sa colonne d'état ; elle n'est pas rechargée automatiquement.

### Entités clés

- **Demande** (existante) : gagne un **avancement** pendant la génération : pourcentage
  et phase en cours, remis à zéro quand la demande est remise en file, effacé à la fin.

## Critères de succès *(obligatoire)*

### Résultats mesurables

- **SC-001** : Sur une génération réelle d'au moins 5 minutes, le pourcentage affiché
  augmente au moins une fois par minute pendant toute la durée de la génération (aucune
  période de plus de 60 s sans progression).
- **SC-002** : Sur cette même génération, aucun pourcentage relevé n'est inférieur au
  relevé précédent, et le pourcentage n'atteint jamais 100 % avant la disponibilité du
  rapport.
- **SC-003** : L'écart entre le pourcentage affiché et la part du temps total écoulée
  reste inférieur à 25 points de pourcentage pendant au moins 80 % de la génération
  (mesure sur Paris 17e ou Courbevoie, durées de chaque phase relevées dans le journal du
  rapport).
- **SC-004** : La durée de génération d'un rapport n'augmente pas de plus de 2 % par
  rapport à la même génération sans suivi de l'avancement.
- **SC-005** : Pendant la seconde moitié des analyses par l'IA, l'estimation de la durée
  restante s'écarte de moins de 2 minutes de la durée restante constatée.
- **SC-006** : Le mainteneur, en essayant la page avant la fusion, juge l'affichage
  compréhensible sans explication (essai des interfaces, LL-031).

## Hypothèses

- La page de suivi existante, rechargée toutes les 30 secondes, reste le support de
  l'affichage ; l'usager peut aussi fermer la page et attendre le courriel (inchangé).
- Le poids relatif des phases (lecture des sources, analyses par l'IA, calcul, mise en
  forme) peut être estimé à partir des durées mesurées des générations réelles ; il n'a
  pas besoin d'être exact, seulement de produire une progression régulière.
- Le nombre de points à analyser par l'IA est connu avant le début de leurs analyses.
- L'avancement est enregistré par le job pendant qu'il travaille, à une fréquence
  modérée (pas à chaque micro-opération), là où la base est de toute façon active.

## Hors périmètre

- Progression de la file d'attente (position, heure estimée : inchangées).
- Notification en temps réel (push, courriel intermédiaire) : seul le courriel de fin
  existe.
- Accélération de la génération elle-même.
- Rechargement automatique de la liste « Mes demandes ».
