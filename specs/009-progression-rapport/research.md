# Recherche : progression en pourcentage de la génération d'un rapport (009)

Toutes les inconnues du contexte technique sont levées ci-dessous. Mesures et lectures de
code du 2026-10-09 (`main` = 4659e71).

## R1 — Où passe le temps d'une génération

**Constat** (journal du rapport de Paris 17e, v0.1.2, 270 points dont 54 P1) : 504 s au
total ; `acquisition` 95 s, `ia` 398 s (44 appels, 10 non évalués : 7,4 s par point P1),
`calcul` 11 s, `rapport` 0,1 s.

**Constat** (code) : `lot/commune.py` enregistre l'étape « acquisition » puis, aussitôt,
« calcul » : les sources sont lues **pendant** le calcul (`_Chronometre` autour du
fournisseur), dans cet ordre :

1. sources globales de la commune (contour, offre IDFM, OSM, BD TOPO, îlots de chaleur,
   altitudes, comptages) ;
2. boucle sur chaque point : sources ponctuelles (végétation, Panoramax) ;
3. `analyse_ia` sur la liste des points P1 : un appel par point (`AnalyseurAge.__call__`) ;
4. fin du calcul, puis rendu du rapport et écriture dans le stockage.

L'étape enregistrée ne dit donc rien de l'avancement réel : elle vaut « calcul » de la
deuxième seconde jusqu'à la fin des analyses. La valeur « démarrage » de la capture de
l'issue correspond à `etape IS NULL`, entre la prise en charge et la première étape.

**Décision** : quatre phases observables, dans l'ordre du code : `sources` (1), `points`
(2), `ia` (3), `rapport` (4, calcul final compris). Les étapes historiques `acquisition` et
`calcul` ne sont plus écrites.

## R2 — Calcul du pourcentage

**Décision** : pourcentage = début de la phase + part faite de la phase × poids de la
phase, avec des bornes fixes tirées de R1 :

| Phase | Libellé affiché | Bornes | Avancement dans la phase |
|---|---|---|---|
| (avant) | démarrage | 0 % | — |
| `sources` | lecture des données | 0 → 5 % | une marche à la fin de la phase |
| `points` | analyse des points | 5 → 20 % | points parcourus / points |
| `ia` | analyse des photos aériennes | 20 → 97 % | points P1 traités / points P1 |
| `rapport` | mise en forme du rapport | 97 → 99 % | une marche |

100 % n'est jamais enregistré : la fin est signalée par l'état `terminee` (FR-004). Une
commune sans point P1 passe directement de 20 à 97 %.

**Justification** : sur Paris 17e, la phase `ia` représente 79 % du temps et occupe 77
points de pourcentage ; les phases 1 et 2 (19 % du temps) en occupent 20. L'écart au temps
écoulé reste sous 25 points (SC-003) même si la part de l'IA varie fortement (cache plein,
commune sans P1 : la marche est rapide mais le pourcentage ne recule jamais).

**Alternatives écartées** : poids appris des générations précédentes (complexité, peu de
données) ; pourcentage par étape seul (figé 80 % du temps, motif de l'issue).

## R3 — Comment le calcul signale son avancement

**Décision** : paramètre facultatif `avancement` (fonction `(phase, fait, total)`) passé à
`calculer_commune` et à `AnalyseurAge`, `None` par défaut. Le calcul reste pur et testable
sans base (principe VII) ; c'est `lot/commune.py` qui fournit une fonction écrivant en
base. Pour la méthode 2.0 (`calculer_avec_v1`), seul le calcul principal reçoit la
fonction ; la comparaison 1.2 réutilise les réponses de l'IA (cache) et ne fait pas
reculer le pourcentage (garde en base, R4).

**Alternatives écartées** : lire l'avancement depuis le `JournalGeneration` partagé
(couplage du calcul au journal du lot) ; fil d'exécution séparé qui sonde l'état
(concurrence inutile).

## R4 — Écriture de l'avancement en base

**Décision** : une écriture au plus toutes les 5 secondes, plus une à chaque changement de
phase, par `UPDATE demande SET avancement = GREATEST(coalesce(avancement, 0), %s), …
WHERE id = %s AND etat = 'en_cours'` :

- `GREATEST` garantit la croissance (FR-003), y compris pour la passe 1.2 de la méthode 2.0 ;
- `etat = 'en_cours'` empêche d'écrire sur une demande remise en file ou terminée ;
- une erreur d'écriture est journalisée et **n'interrompt pas** la génération (le suivi est
  accessoire) ;
- environ 100 écritures pour une génération de 8 minutes, pendant que la base est de toute
  façon active (le job l'utilise) : aucun coût au repos (principe II), coût négligeable
  devant 8 minutes (SC-004).

**Alternatives écartées** : écrire à chaque point (270 + 54 écritures, sans gain visible
avec un rafraîchissement de page de 15 s) ; stocker l'avancement dans le stockage objet
(lecture plus lente par la page, cohérence moins simple).

## R5 — Durée restante

**Décision** : pendant la phase `ia` seulement (clarification Q1), le job calcule
`fin_estimee = maintenant + durée moyenne par point P1 déjà traité × points P1 restants +
15 s` (calcul final et rendu, ≈ 11 s sur Paris 17e) et l'enregistre **en heure absolue**.
La page affiche `fin_estimee − maintenant`, arrondi à la minute supérieure (« environ
N min restantes », « moins d'une minute » sous 60 s, rien si la date est passée). Une heure
absolue reste juste entre deux écritures, contrairement à une durée.

La moyenne est prise sur tous les points P1 déjà traités ; les réponses en cache, presque
instantanées, la font baisser : l'estimation reste prudente quand le cache est vide, et se
corrige à chaque écriture.

**Alternatives écartées** : estimation dès le début à partir de durées habituelles
(imprécise selon la commune, refusée en clarification) ; moyenne glissante sur les
derniers points (plus nerveuse, sans gain mesuré).

## R6 — Mise à jour de la page

**Décision** : la page de suivi garde le rechargement HTML (`meta refresh`), sans script,
avec une période de **15 s** pendant la génération (30 s en file, inchangé). Affichage :
élément `<progress max="100">` (rôle de barre de progression natif, valeur annoncée par
les lecteurs d'écran, FR-007), texte « 42 % — analyse des photos aériennes », durée
restante si connue. La liste « Mes demandes » affiche « en cours (42 %) » (clarification
Q2), sans rechargement.

**Justification** : pas de script ni de point d'accès nouveau (surface d'attaque et CSP
inchangées, principe I) ; 15 s donne au moins quatre mises à jour par minute (SC-001) ;
chaque rechargement lit une ligne de la base, déjà active pendant la génération.

**Alternatives écartées** : sondage en JavaScript d'un point d'accès JSON (script, CSP et
point d'accès à protéger, pour un gain de fluidité seulement) ; flux d'événements serveur
(connexion longue sur un conteneur sans serveur).

## R7 — Déploiement et compatibilité

**Constat** : le job applique les nouvelles migrations à son premier passage
(`lot/__main__.py`, témoin `schema/<n>`), avant de traiter une demande ; l'API lit les
demandes par `SELECT d.*`.

**Décision** : migration `006_avancement.sql` (colonnes facultatives, contrainte d'étape
élargie aux valeurs nouvelles, anciennes conservées pour les lignes existantes). Les
gabarits tolèrent l'absence des colonnes (API déployée avant le premier passage du job) :
sans avancement, la page garde l'affichage actuel.
