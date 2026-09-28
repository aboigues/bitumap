# Constitution de bitumap

bitumap est une plateforme Forward Deployed Engineering de diagnostic des chaussées : pour un
territoire donné, elle classe les points du réseau bus où l'enrobé est le plus exposé au risque
d'orniérage. Elle succède au prototype `docs/reference/prototype-courbevoie-v2.html`. Toute la
documentation du projet (specs, plans, rapports) est rédigée en français.

## Core Principles

### I. Sécurité d'abord (PRIORITÉ ABSOLUE)

- La sécurité prime sur tous les autres principes : en cas de conflit (coût, délai,
  simplicité, fonctionnalité), l'option la plus sûre l'emporte.
- Chaque push et chaque PR déclenche des contrôles automatiques dans GitHub Actions :
  - analyse statique du code (SAST) avec CodeQL ;
  - analyse des dépendances : Dependabot (alertes et mises à jour) et revue des dépendances
    ajoutées dans chaque PR ;
  - recherche de secrets dans le code et l'historique ;
  - analyse des vulnérabilités des images de conteneur et de l'infrastructure as code ;
  - génération d'un SBOM à chaque livraison.
- Une vulnérabilité critique ou élevée bloque la fusion et le déploiement. Une exception
  n'est possible que documentée (raison, date d'expiration, responsable) dans le dépôt.
- Les workflows GitHub Actions ont des permissions minimales (`permissions:` explicites) et
  les actions tierces sont épinglées par SHA de commit.
- Le point d'appel public est authentifié et limité en débit et en coût (quota de rapports
  par client), pour empêcher qu'un abus ne fasse exploser la facture (« denial of wallet »).
- Moindre privilège partout : comptes de service, accès au stockage objet, clés LLM.
- Les vulnérabilités signalées sont traitées selon un `SECURITY.md` publié dans le dépôt.

*Justification* : la plateforme manipule des données de collectivités et déclenche des
dépenses à la demande ; une faille coûte plus cher que n'importe quelle fonctionnalité.

### II. À la demande, zéro coût au repos

- Aucun processus permanent : un rapport est généré uniquement à l'appel, pour un territoire
  (commune ou département). Périmètre V1 : Île-de-France.
- L'infrastructure de calcul DOIT revenir à zéro instance quand aucun rapport n'est demandé.
  Tout composant facturé à l'heure au repos (base de données, VM, cluster) est interdit sauf
  justification écrite dans le plan.
- Les rapports générés et les extractions de sources sont conservés en stockage objet. Un
  rapport est réutilisé tant que l'empreinte de ses sources et la version de méthode n'ont pas
  changé ; il n'est recalculé qu'en cas de changement ou sur demande explicite.

*Justification* : le service est appelé ponctuellement, en mission ; il ne doit rien coûter
entre deux appels.

### III. Souveraineté et traçabilité des sources

- Hébergement chez un fournisseur français (Scaleway ou OVHcloud), calcul et données stockés
  en France.
- Seules des sources ouvertes sont utilisées en V1 : IDFM, OpenStreetMap, IGN (RGE ALTI,
  BD TOPO, orthophotos), Institut Paris Region, Panoramax.
- Chaque rapport DOIT indiquer pour chaque source : nom, licence, URL et date d'extraction.
- Tout appel à un service hors de l'UE (y compris un LLM) est déclaré dans le plan et dans le
  rapport, avec la nature des données transmises.

*Justification* : les clients visés sont des collectivités et gestionnaires de voirie publics.

### IV. Méthode transparente et reproductible (NON NÉGOCIABLE)

- Le score est déterministe et porte un numéro de version de méthode. Même territoire, mêmes
  extractions de sources, même version de méthode : même rapport, au point près.
- Chaque facteur du score (charge, sollicitation, site, chaleur, âge de l'enrobé) est
  affiché et explicable pour chaque point du rapport.
- Toute modification de pondération, de seuil ou de facteur incrémente la version de méthode
  et est décrite dans un journal des changements de méthode.
- Le rapport affiche ses limites : le score classe les points à relever en priorité, il ne
  mesure pas l'état réel de la chaussée.

*Justification* : un classement qui oriente des dépenses publiques doit pouvoir être audité
et rejoué.

### V. IA encadrée

- L'analyse par LLM vision (âge de l'enrobé sur orthophotos, lecture des photos Panoramax)
  est limitée aux points P1.
- Tout résultat issu d'un LLM est marqué « à confirmer » dans le rapport, avec le modèle
  utilisé et la date.
- Un résultat LLM ne détermine jamais seul une priorité : il ne peut que moduler un score
  calculé de façon déterministe, dans les bornes fixées par la méthode.
- Le coût LLM est plafonné par rapport et journalisé (tokens, coût, nombre d'images). Plafond
  atteint : le rapport est produit sans les analyses restantes et le signale.
- Les réponses LLM sont mises en cache avec le rapport pour garantir la reproductibilité
  (principe IV).

*Justification* : l'IA remplace une lecture visuelle manuelle, pas le jugement d'un ingénieur.

### VI. Extensible par le terrain

- Le modèle de données prévoit dès la V1 des relevés terrain rattachés à un point du rapport :
  photos, mesures d'ornière, observations, auteur, date.
- Les relevés sont versionnés et ne modifient jamais le calcul d'origine : ils l'enrichissent
  ou le corrigent dans une couche distincte, et le rapport distingue « estimé » et « constaté ».
- La saisie terrain elle-même relève de la phase 2 ; la V1 n'en fournit que le schéma et les
  identifiants stables des points.

*Justification* : le rapport de bureau est un premier tri, destiné à être confronté au terrain.

### VII. Simplicité et tests

- Pipeline en trois étapes indépendantes : acquisition → calcul → rapport. Chaque étape lit
  et écrit des fichiers intermédiaires versionnés.
- Chaque source est isolée derrière un adaptateur testable avec un jeu de données figé
  (fixtures), sans accès réseau pendant les tests.
- Le cas Courbevoie (prototype v2) sert de test de non-régression : tout écart de rang doit
  être expliqué par un changement de méthode ou de source.
- YAGNI : pas de micro-services, d'orchestrateur ou de base de données tant qu'un besoin
  mesuré ne l'exige pas.

### VIII. Retour d'expérience systématique

- Chaque incident, bug ou problème rencontré (en développement, en CI, en production ou dans
  la méthode de score) DOIT donner lieu à une entrée dans `LESSON-LEARNED.md`, à la racine
  du dépôt, au plus tard dans la PR qui le corrige.
- Chaque entrée contient : date, contexte, symptôme observé, analyse des causes racines
  (méthode des « 5 pourquoi » ou équivalent), correctif appliqué, mesure préventive (test,
  règle, contrôle CI, amendement) et lien vers le commit ou la PR.
- Une leçon n'est close que si sa mesure préventive existe : un bug corrigé sans test ou
  contrôle qui empêche sa réapparition reste ouvert.
- Le fichier est lu au début de chaque session de travail, humaine ou assistée par IA ; il
  est chargé automatiquement dans le contexte des agents de code du projet.
- Une leçon qui se répète ou qui touche un principe déclenche une proposition d'amendement de
  cette constitution.
- Les incidents de sécurité y figurent sans aucun secret ni détail exploitable ; le détail
  reste dans un avis de sécurité privé (principe I).

*Justification* : sans trace écrite des causes racines, les mêmes erreurs reviennent d'une
session à l'autre, en particulier avec des agents IA qui repartent sans mémoire.

### IX. Agents IA : proposer, jamais fusionner

- Un agent IA ne travaille que sur une branche dédiée à sa tâche. Il ne commite ni ne pousse
  jamais sur `main`, et ne réécrit jamais l'historique d'une branche partagée (pas de
  `push --force` sur `main`).
- Un agent IA peut ouvrir une PR depuis sa branche dédiée ; il ne peut ni l'approuver, ni la
  fusionner, ni fusionner celle d'un autre agent. La fusion est un acte humain.
- Un agent IA ne contourne jamais une protection : pas de désactivation de contrôle CI, pas
  de modification des règles de branche, pas d'usage d'un droit administrateur ou de
  contournement (« bypass »).
- Ces règles sont appliquées techniquement, pas seulement par consigne :
  - règles de protection de `main` : PR obligatoire, au moins une approbation humaine,
    contrôles requis au vert (principe I), aucun contournement autorisé ;
  - les identifiants utilisés par les agents n'ont ni droit administrateur, ni droit de
    contournement, ni droit de fusion ;
  - un fichier `CODEOWNERS` impose une revue humaine sur `.github/`, sur cette constitution
    et sur la méthode de score.

*Justification* : l'agent accélère la production, l'humain reste responsable de ce qui entre
dans `main`, en particulier pour la sécurité et la méthode de score.

## Contraintes techniques et données

- Une génération de rapport est un traitement asynchrone : l'appel renvoie un identifiant,
  le rapport est consultable une fois prêt. La durée cible et le plafond de coût par rapport
  sont fixés dans le plan.
- Les photos (Panoramax, puis relevés terrain) peuvent contenir des données personnelles
  (visages, plaques) : elles ne sont ni republiées ni transmises à un tiers sans floutage ou
  base légale documentée (RGPD).
- Les secrets (clés API, accès stockage) sont fournis par variables d'environnement ou
  gestionnaire de secrets du fournisseur, jamais dans le dépôt.
- Dépendances et images de base : dernière version stable vérifiée au moment de l'ajout.

## Flux de développement

- Chaque fonctionnalité suit le flux Spec Kit : `/speckit-specify` → `/speckit-clarify` si
  besoin → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`, sur une branche dédiée.
- Le « Constitution Check » du plan vérifie explicitement les principes I à IX, en commençant par la sécurité ; toute
  exception est justifiée dans la section de suivi de complexité du plan.
- Une PR n'est fusionnée que si les tests passent, y compris la non-régression Courbevoie,
  si tous les contrôles de sécurité GitHub Actions sont au vert (branche `main` protégée)
  et, pour une correction, si l'entrée `LESSON-LEARNED.md` correspondante est incluse.
- La fusion d'une PR est toujours réalisée par un humain, après sa propre relecture
  (principe IX).

## Governance

- Cette constitution prévaut sur toute autre pratique du projet ; au sein de la constitution,
  le principe I (sécurité) prévaut sur les autres.
- Amendement : par PR modifiant ce fichier, avec description de l'impact sur les specs et
  plans en cours.
- Versionnement sémantique : MAJEUR pour la suppression ou la redéfinition d'un principe,
  MINEUR pour un ajout ou un élargissement, CORRECTIF pour une clarification.
- Chaque revue de PR vérifie la conformité aux principes ; la version de méthode de score
  (principe IV) est distincte de la version de cette constitution.

**Version**: 1.3.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-09-28
