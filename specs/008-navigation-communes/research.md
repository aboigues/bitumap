# Recherche (phase 0) : navigation et recherche de communes

Mesures faites le 2026-10-08 sur `geo.api.gouv.fr` et sur le code de `main` (6f781a1).

## R1 — Source de la liste intégrée

- **Décision** : liste générée depuis l'API Géo (`geo.api.gouv.fr`, Licence Ouverte 2.0,
  déjà utilisée par 002) et **versionnée dans le paquet** (`territoire/communes_idf.json`),
  avec sa source, sa licence et sa date de génération. Requêtes :
  `/communes?codeRegion=11&fields=nom,code,codeDepartement` et
  `/communes?codeRegion=11&type=arrondissement-municipal&fields=nom,code,codeDepartement`.
  La commune `75056` (Paris entier) est **retirée** : un rapport porte sur un arrondissement
  (002, LL-027).
- **Mesure** : 1 266 communes (dont `75056`) et 20 arrondissements, soit **1 285 entrées**
  après retrait ; environ 36 Ko en JSON compact. Quatre noms existent en double dans deux
  départements (Blandy, Marolles-en-Brie, Mondreville, Saint-Martin-des-Champs) : le
  département est indispensable à l'affichage (FR-004).
- **Mise à jour** : script `scripts/territoire/liste_communes.py`, lancé à la main (le
  référentiel change au plus une fois par an, au 1er janvier) ; le fichier produit passe en
  revue dans une PR. Aucun appel réseau à l'exécution du service ni en test (principe VII).
- **Alternatives écartées** : appel à l'API Géo pendant la frappe (rejeté par le
  mainteneur, dépendance et fuite des frappes vers un tiers) ; fichier COG de l'INSEE (CSV
  plus lourd à filtrer, même contenu pour notre besoin).

## R2 — Où se fait la correspondance : serveur

- **Décision** : la correspondance (normalisation, classement, limite de 10) est faite
  **par l'API**, sur la liste chargée une fois en mémoire ; le navigateur n'en reçoit que
  les 10 propositions. Une seule implémentation, testée en Python, sert les deux modes :
  - sans script : formulaire `GET /communes?q=…` → page de résultats (FR-006) ;
  - avec script : `GET /communes/recherche?q=…` (JSON) appelé pendant la frappe par un
    petit script statique (`/statique/communes.js`), autorisé par la CSP actuelle
    (`script-src 'self'`), sans modification de celle-ci.
- **Performance** : 1 285 entrées parcourues en mémoire, bien moins d'une milliseconde ;
  SC-002 (0,3 s) dépend surtout du réseau ; frappe temporisée à 150 ms, requête précédente
  annulée.
- **Alternatives écartées** : envoyer la liste entière au navigateur et filtrer en
  JavaScript (deux implémentations de la normalisation à garder identiques, et rien sans
  script) ; `<datalist>` natif (correspondance des navigateurs sensible aux accents, ce qui
  viole FR-002, et ne porte pas le code INSEE).

## R3 — Normalisation et classement

- **Décision** : forme de recherche = nom en minuscules, sans accents (décomposition
  Unicode NFKD, marques diacritiques retirées), `-`, `'`, `’` et espaces multiples ramenés à
  un espace, `st`/`ste` en tête de mot remplacés par `saint`/`sainte`. Même traitement pour
  la saisie. Pour les arrondissements, alias ajoutés : `paris 17`, `paris 17e`, `17e` (et
  `1er` pour le premier).
- **Classement** : 0 = la forme commence par la saisie ; 1 = un mot de la forme commence
  par la saisie ; 2 = la saisie est contenue ; puis ordre alphabétique et département.
  Au plus 10 résultats ; saisie normalisée de moins de 3 caractères ⇒ seulement une
  correspondance exacte du nom (« us » ⇒ Us, 95, seul nom de 2 lettres en Île-de-France ;
  clarification du 2026-10-08), sinon aucune proposition. Le script n'appelle l'API qu'à
  partir de 2 caractères.
- **Codes** : 5 chiffres ⇒ recherche par code postal actuelle (R4) ; aucune recherche par
  code INSEE (non demandée, retirée en clarification).
- **Vérification SC-001** : test qui parcourt les 1 285 entrées ; nom complet ⇒ présent ;
  lettres nécessaires (début du nom) : médiane 3, 99,1 % en 7 au plus, maximum 10 (mesure
  du 2026-10-08 ; « Saint », « Ville » et « Paris » empêchent toute cible à 5 lettres).
  Saisie sans espace ni apostrophe acceptée (« lhay » ⇒ L'Haÿ-les-Roses). Durée mesurée :
  0,4 ms par recherche.

## R4 — Code postal : recherche actuelle conservée

- **Décision** (clarification Q3) : un code postal à 5 chiffres continue d'appeler
  `territoire.communes_du_code_postal` (API Géo), sans changement de résultat. Si l'API Géo
  est indisponible, l'erreur actuelle est remplacée par un message invitant à chercher par
  le nom (FR-003). La recherche par nom n'en dépend jamais.

## R5 — Menu et fil d'Ariane dans les pages du service

- **Décision** : dans `base.html`, un `<nav aria-label="Menu principal">` construit à partir
  d'une liste d'entrées définie **en Python** (`api/navigation.py`) : libellé, adresse,
  rubrique, condition (connecté, mainteneur). Chaque gabarit déclare sa rubrique et son
  fil (`rubrique`, `fil` dans le contexte, ou variables `{% set %}` du gabarit). L'entrée
  courante porte `aria-current="page"` et un style non fondé sur la seule couleur
  (soulignement épais) (FR-009).
- **Téléphone** (clarification Q4) : `<details class="menu"><summary>Menu</summary>…`
  natif, qui s'ouvre et se ferme **sans script** ; au-delà de 48 em, une seconde liste
  (`.large`) est affichée et le `details` masqué. L'une des deux est toujours en
  `display: none`, donc ignorée des lecteurs d'écran. Écarté à l'implémentation : forcer
  l'affichage du contenu d'un `details` fermé par CSS, non fiable selon les navigateurs
  (`::details-content`). Aucun script, aucune modification de CSP.
- **Fil d'Ariane** : `<nav aria-label="Fil d'Ariane"><ol>` ; dernier élément sans lien,
  `aria-current="page"` ; absent de l'accueil (FR-011).
- **Mainteneur** : fonction globale des gabarits `est_mainteneur(session)` (réutilise
  `api/auth.est_mainteneur`) ; « Modération » n'est jamais rendue pour un autre compte
  (FR-013).
- **Page d'erreur** : le gestionnaire d'erreurs ne passe pas la session au gabarit ;
  il appellera `session_courante(requete)` pour que le menu reflète le compte connecté.
  Une erreur pendant la lecture de la session ⇒ menu de visiteur (jamais d'erreur en
  cascade).
- **Alternatives écartées** : menu « hamburger » piloté par script (CSP, sans script
  inopérant) ; barre d'onglets en bas (écartée en clarification).

## R6 — Menu dans le rapport, ajouté au service

- **Constat** : le rapport stocké est figé (LL-011) ; il est servi par
  `api/demandes.rapport`, qui y insère déjà les relevés (`_inserer_avant_script`). Sa CSP
  (`rendu.csp_du_document`) autorise `style-src 'unsafe-inline'`, `img-src data:`,
  `form-action 'none'`, et seulement les scripts en ligne présents dans le document.
- **Décision** : à chaque service, insertion juste après la balise `<body>` d'un fragment
  rendu par un gabarit de l'API (`rapport_menu.html`) : `<style>` propre, préfixé
  (`.bm-…`), utilisant les variables de couleur du rapport (thème sombre compris), menu
  `<details>` identique à R5 et fil « Accueil › Mes demandes › <commune> ». **Aucun
  script, aucun formulaire** : le bouton « Se déconnecter » n'y figure pas (`form-action
  'none'`, que l'on garde) ; « Mon compte » y mène. Le menu dépend de la **session qui
  consulte** (FR-015). Rapports anciens : même insertion, la balise `<body>` existe dans
  toutes les versions du gabarit (vérifié sur `rapport.html.j2`).
- **Ordre des insertions** : le menu va après `<body>`, les relevés restent après le bloc
  `donnees` ; test sur un rapport produit par une version antérieure (règle de LL-011) et
  essai navigateur obligatoire (règle de LL-012, LL-017 : filtres, carte, fiche).
- **Hors ligne** : un rapport enregistré garde le menu, inopérant sans réseau ; aucune
  autre conséquence.
- **Alternatives écartées** : menu écrit dans le rapport à la génération (figé : ne
  dépendrait pas du compte qui consulte, absent des rapports en cache, et ferait changer
  l'empreinte) ; `form-action 'self'` pour garder la déconnexion (affaiblit la CSP du
  rapport sans besoin).

## R7 — « Communes ayant un rapport disponible »

- **Décision** : candidates = `commune_insee` des demandes `terminee` depuis moins de
  `cache_rapport_jours` (table `demande` ; aucun index ne couvre ce filtre, inutile au
  volume de la V1 : quelques centaines de demandes, lecture séquentielle) ; retenue si l'empreinte
  de la demande la plus récente vaut `versions.empreinte_courante(insee)` (calcul local,
  sans appel au stockage), ce qui reprend la règle de `rapport_valide`. La page de choix
  ne montre ni le demandeur ni la date de demande (clarification Q1).
- **Pages** : `GET /terrain` et `GET /parcours` (nouvelles, sans `insee`) : champ de
  recherche (R2), liste des communes disponibles ; une commune trouvée mais sans rapport
  disponible propose « Demander le rapport » (vers la page de confirmation de 002). Les
  pages `/terrain/{insee}` et `/parcours/{insee}` existantes ne changent pas.
- **Volume** : quelques dizaines de communes au plus pendant la V1 ; aucune pagination.

## R8 — Données personnelles et sécurité

- Les frappes de recherche ne quittent pas le service (aucun appel tiers) ; elles ne sont
  pas journalisées (même règle que les adresses de 006).
- `GET /communes/recherche` : session requise, réponse JSON de 10 entrées au plus, saisie
  bornée à 100 caractères ; pas de quota (aucun coût, calcul en mémoire), mais réponses
  `Cache-Control: private, max-age=3600` sans donnée de compte.
- Aucune nouvelle dépendance, aucune modification de CSP des pages ; CSP du rapport
  inchangée (SC-006).
