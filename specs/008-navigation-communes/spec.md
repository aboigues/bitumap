# Spécification : menu de navigation, fil d'Ariane et recherche de commune par nom

**Branche** : `008-navigation-communes`

**Créée le** : 2026-10-08

**Statut** : brouillon

**Origine** : anomalies 1 et 4 signalées par le mainteneur après les premiers usages en
production (2026-10-07). Décisions du mainteneur (2026-10-08) : menu **oui, avec fil
d'Ariane** ; recherche de commune avec **liste des communes d'Île-de-France intégrée** au
service ; passage par le flux Spec Kit.

## Contexte

Aujourd'hui, une fois connecté, l'utilisateur arrive sur « Demander un rapport » et doit
saisir un **code postal** ; les autres pages (Mes demandes, Mon compte) ne sont reliées que
par deux liens en bas de l'accueil. Les relevés terrain et le parcours de surveillance ne
sont accessibles **que depuis un rapport** (fiche d'un point, bouton « Préparer un
parcours »). Il n'existe ni menu commun, ni repère de l'endroit où l'on se trouve : après
une page d'erreur ou un lien ouvert depuis un courriel, l'utilisateur ne sait pas comment
rejoindre les autres fonctions. Beaucoup d'utilisateurs connaissent le **nom** de leur
commune mais pas tous ses codes postaux (communes à plusieurs codes, arrondissements de
Paris).

## Clarifications

### Session 2026-10-08

- Q : Quelles communes proposer depuis « Relevés terrain » et « Parcours » ? → R : toutes
  les communes ayant un rapport disponible, quel que soit le compte qui l'a demandé (sans
  indiquer qui).
- Q : Le rapport HTML doit-il proposer un retour au service ? → R : oui, le même menu
  complet que les autres pages, intégré au rapport.
- Q : Le code postal passe-t-il aussi par la liste intégrée ? → R : non ; le nom passe par
  la liste intégrée, le code postal garde la recherche actuelle (API Géo).
- Q : Comment s'affiche le menu sur téléphone ? → R : bouton « Menu » qui ouvre la liste
  sur téléphone ; menu affiché en entier sur grand écran.
- Q : À partir de combien de lettres la recherche par nom propose-t-elle des communes ?
  → R : 3 lettres (demande du mainteneur, récit 1) ; en dessous, seule une commune dont le
  nom correspond exactement à la saisie est proposée (cas d'Us, 95, seul nom de 2 lettres).

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Trouver sa commune par son nom (priorité : P1)

Un agent connecté veut le rapport de sa commune. Il commence à taper le nom (« courbe »,
« asnieres », « paris 17 ») et voit aussitôt une courte liste de communes d'Île-de-France
correspondantes, avec leur département ; il en choisit une et demande le rapport, sans
connaître le code postal.

**Pourquoi cette priorité** : c'est l'entrée principale du service ; le code postal seul
fait échouer ou hésiter une partie des utilisateurs (anomalie 4).

**Test indépendant** : depuis l'accueil connecté, taper un début de nom, choisir une
proposition, demander le rapport ; la demande créée porte la bonne commune.

**Scénarios d'acceptation** :

1. **Étant donné** un utilisateur connecté sur l'accueil, **quand** il tape « courbe »,
   **alors** « Courbevoie (92) » figure parmi les propositions.
2. **Étant donné** la saisie « asnieres » (sans accent ni tiret), **quand** les
   propositions s'affichent, **alors** « Asnières-sur-Seine (92) » y figure.
3. **Étant donné** la saisie « paris 17 » ou « 17e », **quand** les propositions
   s'affichent, **alors** « Paris 17e Arrondissement (75) » y figure ; la saisie « paris »
   propose les 20 arrondissements.
4. **Étant donné** la saisie d'un code postal à 5 chiffres (« 92400 »), **quand** les
   propositions s'affichent, **alors** ce sont les communes couvertes par ce code
   (comportement actuel conservé).
5. **Étant donné** une commune choisie, **quand** l'utilisateur demande le rapport,
   **alors** la demande suit le parcours existant (vérification anti-robot, quotas, suivi)
   sans autre changement.
6. **Étant donné** un nom hors d'Île-de-France (« Lyon »), **quand** l'utilisateur le tape,
   **alors** aucune proposition n'apparaît et un message indique que le service couvre
   l'Île-de-France seulement.

---

### Récit 2 — Menu commun à toutes les pages (priorité : P1)

Sur n'importe quelle page du service, rapport compris, l'utilisateur
connecté dispose d'un menu : **Accueil**, **Mes demandes**, **Relevés terrain**,
**Parcours**, **Mon compte**, et, pour le mainteneur seulement, **Modération**. L'entrée
de la page courante est signalée. Sur téléphone, le menu reste utilisable d'une main.

**Pourquoi cette priorité** : sans menu, les fonctions de 003 (relevés) et 006 (parcours)
ne sont trouvables que depuis un rapport, et l'utilisateur perdu ne sait pas revenir où il
était (anomalie 1).

**Test indépendant** : depuis chaque page connectée, chaque entrée du menu mène à la bonne
page ; l'entrée courante est signalée ; « Modération » n'apparaît que pour le mainteneur.

**Scénarios d'acceptation** :

1. **Étant donné** un utilisateur connecté sur « Mon compte », **quand** il choisit « Mes
   demandes » dans le menu, **alors** il arrive sur la liste de ses demandes et l'entrée
   « Mes demandes » est signalée comme page courante.
2. **Étant donné** un utilisateur connecté qui choisit « Relevés terrain » ou « Parcours »,
   **quand** la page s'ouvre, **alors** il choisit une commune (même recherche par nom que
   le récit 1) parmi celles qui ont un rapport disponible, puis arrive sur la page
   existante de cette commune ; si aucun rapport n'est disponible pour la commune cherchée,
   la page propose de le demander.
3. **Étant donné** un utilisateur qui n'est pas le mainteneur, **quand** une page
   s'affiche, **alors** l'entrée « Modération » est absente (et l'adresse de modération
   reste refusée, comme aujourd'hui).
4. **Étant donné** un visiteur non connecté, **quand** une page publique s'affiche
   (accueil-connexion, données personnelles, erreur), **alors** le menu ne montre que ce qui
   lui est accessible (Accueil, Données personnelles) et aucune entrée menant à une page
   réservée.
5. **Étant donné** un écran de téléphone (largeur 360 px), **quand** la page s'affiche,
   **alors** le menu est replié derrière un bouton « Menu » ; **quand** l'utilisateur
   l'ouvre, **alors** toutes les entrées sont visibles et actionnables sans défilement
   horizontal. Sur un grand écran, le menu est affiché en entier, sans bouton.
6. **Étant donné** un rapport ouvert, y compris un rapport produit avant la mise en
   service de cette fonctionnalité, **quand** il s'affiche, **alors** il porte le même menu
   que les autres pages, adapté au compte qui le consulte (« Modération » pour le
   mainteneur seulement), et ses filtres, sa carte et ses fiches fonctionnent comme avant.

---

### Récit 3 — Fil d'Ariane (priorité : P2)

Sous l'en-tête, un fil d'Ariane indique où se trouve l'utilisateur et permet de remonter
d'un ou plusieurs niveaux, par exemple « Accueil › Relevés terrain › Courbevoie › Point
A27418 » ou « Accueil › Mes demandes › Courbevoie ».

**Pourquoi cette priorité** : utile surtout dans les pages profondes (saisie d'un relevé,
résultat d'un parcours) ; le menu (P1) couvre déjà les déplacements principaux.

**Test indépendant** : sur chaque page profonde, le fil affiche le chemin attendu ; chaque
élément sauf le dernier est un lien vers la page correspondante.

**Scénarios d'acceptation** :

1. **Étant donné** la page de saisie d'un relevé pour un point de Courbevoie, **quand**
   elle s'affiche, **alors** le fil est « Accueil › Relevés terrain › Courbevoie › Point
   <identifiant> », et « Courbevoie » mène à la liste des points de la commune.
2. **Étant donné** le résultat d'un parcours, **quand** il s'affiche, **alors** le fil est
   « Accueil › Parcours › <commune> › Résultat ».
3. **Étant donné** la page d'accueil, **quand** elle s'affiche, **alors** aucun fil
   d'Ariane n'est affiché (premier niveau).
4. **Étant donné** un lecteur d'écran, **quand** il parcourt la page, **alors** le fil est
   annoncé comme fil d'Ariane et la page courante est identifiée comme telle.

---

### Cas limites

- Homonymes et noms proches (« Saint-… », « Le Plessis-… ») : les propositions affichent
  le département pour les distinguer ; au plus 10 propositions, les plus pertinentes en
  premier (début de nom avant contenu du nom).
- Saisie avec accents, majuscules, tirets, apostrophes ou « St » pour « Saint » : même
  résultat que la forme officielle.
- Saisie de 1 ou 2 lettres : aucune proposition, sauf nom identique (Us) ; la page sans
  script indique de saisir au moins 3 lettres.
- Commune fusionnée ou renommée depuis la constitution de la liste : la liste suit le
  dernier référentiel officiel au moment de la version ; une commune absente est signalée
  par un message clair, sans erreur.
- Navigateur sans JavaScript ou script bloqué : la recherche reste possible (envoi du
  formulaire, résultats sur une page), comme le code postal aujourd'hui.
- Session expirée en cours de navigation : le menu et le fil n'exposent aucune donnée ;
  le retour à la page voulue après connexion (LL-030) reste valable.
- Service externe des codes postaux indisponible : message invitant à chercher par le
  nom ; la recherche par nom n'en dépend pas.
- Page d'erreur : le menu est présent ; le fil se limite à « Accueil ».
- Rapport enregistré pour une consultation hors ligne : le menu y figure mais ses liens
  ne fonctionnent qu'en ligne ; le contenu du rapport reste lisible.
- Rapport produit avant cette fonctionnalité (encore en cache) : il reçoit le menu comme
  les nouveaux.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : Le service DOIT permettre de trouver une commune ou un arrondissement de
  Paris d'Île-de-France par son nom, ou un début de nom, depuis l'accueil connecté.
- **FR-002** : La recherche DOIT ignorer accents, casse, tirets, apostrophes et espaces
  multiples, et reconnaître « St »/« Ste » pour « Saint »/« Sainte ».
- **FR-003** : Le même champ DOIT accepter aussi un code postal à 5 chiffres, traité par
  la recherche par code postal actuelle (service externe de référence), sans changement de
  résultat ; si ce service est indisponible, un message invite à chercher par le nom.
- **FR-004** : Les propositions DOIVENT afficher le nom officiel et le département, être
  limitées à 10, et classer les noms commençant par la saisie avant les autres.
- **FR-005** : La liste des communes servant à la recherche par nom DOIT être intégrée au service
  (aucun appel à un service externe pendant la frappe), issue d'un référentiel officiel
  sous licence ouverte, avec sa source, sa licence et sa date de mise à jour indiquées
  (principe III) et un moyen documenté de la mettre à jour.
- **FR-006** : La recherche DOIT fonctionner sans JavaScript (formulaire envoyé, résultats
  sur une page) ; avec JavaScript, les propositions s'affichent pendant la frappe.
- **FR-007** : Une saisie ne correspondant à aucune commune d'Île-de-France DOIT produire
  un message explicite, sans erreur technique.
- **FR-008** : Toutes les pages servies par le service, rapport compris, DOIVENT afficher
  le même menu : Accueil, Mes demandes, Relevés terrain, Parcours, Mon compte pour un
  utilisateur connecté ; Modération en plus pour le mainteneur seulement ; Accueil et
  Données personnelles pour un visiteur non connecté.
- **FR-009** : Le menu DOIT signaler l'entrée correspondant à la page courante, de façon
  perceptible sans la couleur seule et annoncée aux technologies d'assistance.
- **FR-010** : Les entrées « Relevés terrain » et « Parcours » DOIVENT mener à un choix de
  commune (même recherche que FR-001) limité aux communes ayant un rapport disponible,
  quel que soit le compte qui l'a demandé, puis aux pages existantes de la commune
  choisie ; la liste NE DOIT PAS indiquer quel compte a demandé le rapport ; pour une commune sans rapport
  disponible, la page DOIT proposer de demander le rapport.
- **FR-011** : Les pages de deuxième niveau et plus DOIVENT afficher un fil d'Ariane dont
  chaque élément, sauf le dernier (page courante), est un lien ; la page d'accueil n'en
  affiche pas.
- **FR-012** : Le menu et le fil d'Ariane DOIVENT rester utilisables sur un écran de 360 px
  de large, au clavier seul et avec un lecteur d'écran. Sur un écran étroit, le menu est
  replié derrière un bouton « Menu » qui s'ouvre et se referme même sans JavaScript ; sur
  un grand écran, il est affiché en entier.
- **FR-013** : Le menu et le fil d'Ariane NE DOIVENT révéler aucune donnée réservée
  (adresse d'un autre compte, existence d'une page de modération pour un non-mainteneur)
  et NE DOIVENT pas affaiblir la politique de sécurité des pages (aucun script ni
  ressource tierce ajouté, principe I).
- **FR-014** : Le libellé des liens existants entre pages (bas de l'accueil, « Autre code
  postal ») DOIT être mis en cohérence avec le menu, sans doublon inutile.
- **FR-015** : Dans le rapport, le menu DOIT correspondre au compte qui consulte (et non
  au compte qui a demandé le rapport), s'appliquer aussi aux rapports produits avant cette
  fonctionnalité, et ne DOIT ni modifier le rapport stocké ni affaiblir sa politique de
  sécurité (aucun script ni ressource tierce ajouté).
- **FR-016** : La recherche par nom DOIT proposer des communes dès la 3e lettre saisie ;
  avec 1 ou 2 lettres, elle NE DOIT proposer qu'une commune dont le nom correspond
  exactement à la saisie (« us » ⇒ Us) ; la même règle vaut avec et sans JavaScript.

### Entités clés

- **Commune de référence** : commune ou arrondissement d'Île-de-France ; code INSEE, nom
  officiel, forme de recherche (sans accents ni ponctuation), département.
  Source, licence et date du référentiel conservées avec la liste.
- **Entrée de menu** : libellé, destination, condition d'affichage (connecté, mainteneur).
- **Élément de fil d'Ariane** : libellé et destination ; le dernier élément est la page
  courante, sans lien.

## Critères de succès *(obligatoire)*

### Résultats mesurables

- **SC-001** : Pour 100 % des communes et arrondissements d'Île-de-France, la saisie du nom
  officiel complet fait apparaître la commune parmi les propositions ; pour 95 % d'entre
  eux, les 5 premières lettres suffisent à la faire apparaître parmi les 10 propositions.
- **SC-002** : Les propositions apparaissent en moins de 0,3 s après une frappe, sur un
  téléphone d'entrée de gamme.
- **SC-003** : Depuis n'importe quelle page connectée, chacune des fonctions principales
  (demander un rapport, mes demandes, relevés terrain, parcours, compte) est atteignable en
  2 actions au plus.
- **SC-004** : Lors d'un essai avec le mainteneur, une commune est trouvée et demandée en
  moins de 30 s sans connaître son code postal (Courbevoie, Asnières-sur-Seine, Paris 17e).
- **SC-005** : Aucun défaut d'accessibilité bloquant (navigation au clavier, nom accessible
  du menu et du fil, page courante annoncée) sur les pages modifiées.
- **SC-006** : La politique de sécurité des pages et les contrôles requis de la CI sont
  inchangés ou plus stricts.

## Hypothèses

- « Rapport disponible » (FR-010) : rapport déjà produit et encore servi pour la commune
  (accès déjà ouvert à toute session connectée, vérifié dans le code).
- Le rapport reçoit le menu ; le fil d'Ariane y suit FR-011 (« Accueil › Mes demandes ›
  <commune> ») si la planification le juge compatible avec sa mise en page.
- La liste intégrée est mise à jour avec les versions du service (le référentiel des
  communes change au plus une fois par an). La recherche par code postal garde son appel
  actuel au service externe (clarification du 2026-10-08).
- Les pages existantes (relevés, parcours, modération, suivi) gardent leurs adresses ; seuls
  l'en-tête, le menu, le fil et l'accueil changent.
- Le service reste en français uniquement.
- Les « autres éléments d'interface » annoncés par le mainteneur et non encore décrits
  feront l'objet de `/speckit-clarify` ou d'une fonctionnalité ultérieure.

## Hors périmètre

- Recherche d'une adresse ou d'une rue (déjà prévue par le parcours, 006).
- Recherche de communes hors d'Île-de-France.
- Refonte graphique générale du service.
