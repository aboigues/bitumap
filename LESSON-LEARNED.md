# Retours d'expérience (LESSON-LEARNED)

Fichier imposé par le principe VIII de la constitution (`.specify/memory/constitution.md`).
Il est lu au début de chaque session de travail, humaine ou IA (chargé via `CLAUDE.md`).

## Règles

- Une entrée par incident, bug ou problème rencontré, ajoutée au plus tard dans la PR qui le
  corrige.
- Les entrées les plus récentes sont en haut.
- Une leçon est **ouverte** tant que sa mesure préventive (test, contrôle CI, règle,
  amendement) n'existe pas.
- Aucun secret ni détail exploitable : un incident de sécurité renvoie vers un avis de
  sécurité privé.
- Une leçon qui se répète ou touche un principe déclenche une proposition d'amendement de la
  constitution.

## Modèle d'entrée

```markdown
### LL-NNN — Titre court (AAAA-MM-JJ) — Ouverte | Close

- **Contexte** : où et quand (développement, CI, production, méthode de score).
- **Symptôme** : ce qui a été observé, message d'erreur exact si court.
- **Causes racines** :
  1. Pourquoi ? …
  2. Pourquoi ? …
  3. Pourquoi ? … (jusqu'à la cause sur laquelle on peut agir)
- **Correctif** : ce qui a été changé.
- **Mesure préventive** : test, contrôle CI, règle ou amendement qui empêche la récidive.
- **Références** : commit, PR, issue.
```

## Entrées

### LL-010 — Fichier d'une autre branche recréé par un éditeur ouvert (2026-09-29) — Close

- **Contexte** : développement, spécifications 003 à 007 sur des branches successives, dépôt
  sous `/mnt/c` (WSL) ouvert en parallèle dans un éditeur Windows.
- **Symptôme** : sur la branche `006-parcours-surveillance`, `specs/004-methode-v2/spec.md`
  apparaît « non suivi » (version brouillon, fins de ligne CRLF) ; supprimé, il revient en
  45 s.
- **Causes racines** :
  1. Pourquoi réapparaît-il ? Un éditeur Windows avait ce fichier ouvert : après le
     `git switch` qui le retirait, l'éditeur l'a réenregistré avec son contenu en mémoire.
  2. Pourquoi le brouillon ? L'éditeur tenait la version ouverte avant les clarifications ;
     les fins de ligne CRLF trahissent l'enregistrement côté Windows.
  3. Pourquoi soupçonner d'abord kDrive ? Symptôme identique à LL-002 ; la fermeture du
     fichier par le mainteneur a supprimé la recréation (vérifié : aucune réapparition en
     60 s), ce qui met kDrive hors de cause.
- **Correctif** : fichier fermé dans l'éditeur, copie parasite supprimée ; rien n'avait été
  commité (ajouts par chemins explicites, LL-002).
- **Mesure préventive** : fermer dans l'éditeur les fichiers d'une branche avant d'en changer
  (ou désactiver la restauration automatique des fichiers supprimés) ; relire `git status`
  après chaque changement de branche et n'ajouter que des chemins explicites. Un fichier
  non suivi en CRLF sur une branche où il n'existe pas signale un réenregistrement Windows.
- **Références** : branche `007-projection-ete`.

### LL-009 — Coût IA du jour arrondi à chaque opération (2026-09-29) — Close

- **Contexte** : développement US4, test du plafond de coût par rapport
  (`tests/unit/test_journal.py`).
- **Symptôme** : dépense d'un rapport ≤ 0,002 €, mais cumul du jour enregistré à 0,0021 €.
- **Causes racines** :
  1. Pourquoi l'écart ? `cout_ia_jour.montant_eur` était en `numeric(10, 4)` : chaque
     réservation (≈ 0,0004 €) et chaque ajustement étaient arrondis au dix-millième.
  2. Pourquoi 4 décimales ? Choisies à l'échelle de l'euro, sans rapprocher du coût d'un
     appel (≈ 0,0003 €, R7-bis), du même ordre que la précision.
  3. Pourquoi non vu plus tôt ? Les tests du budget comparaient des plafonds larges au
     cumul, jamais le cumul du jour à la somme exacte des dépenses.
- **Correctif** : migration `002` : `numeric(12, 6)` pour `cout_ia_jour.montant_eur` et
  `lot.cout_ia_eur`.
- **Mesure préventive** : test du plafond serré (0,002 €) comparant le cumul du jour à la
  dépense réelle. Règle : la précision d'un montant stocké est choisie à partir de la plus
  petite opération (ici un appel), pas de l'unité affichée.
- **Références** : branche `002-us4-couts-suivi`.

### LL-008 — Arrêt sous un pont classé Critique (2026-09-29) — Close

- **Contexte** : méthode de score, rapport de Courbevoie, issue #18 ouverte par le mainteneur.
- **Symptôme** : « Verdun - Rue Latérale » (A27418) classé Critique (rang 4) avec « plein
  soleil l'été : 10,5 h/jour », alors que le bus s'arrête sous le pont ferroviaire de la ligne
  Saint-Lazare – Versailles.
- **Causes racines** :
  1. Pourquoi 10,5 h ? La grille d'ombres ne contenait que les bâtiments et les arbres ; les
     tabliers de ponts n'existaient pas pour le calcul.
  2. Pourquoi ignorés ? Méthode reprise du prototype, qui ne les modélisait pas, et la
     non-régression compare au prototype : elle ne pouvait pas révéler le défaut.
  3. Pourquoi ajouter les ponts ne suffisait pas (7,5 h) ? L'ensoleillement était mesuré en un
     seul point, projection du poteau, ici au bord du tablier ; or le bus s'arrête en amont
     du poteau, sous le pont.
- **Correctif** : méthode 1.2 : tabliers OSM dans la grille d'ombres, mesure d'un arrêt sur
  sa zone d'arrêt (12 m en amont, 5 points) ; A27418 : 1,5 h, rang 63, À surveiller.
- **Mesure préventive** : tests `tests/unit/test_ouvrages.py` (chaussée sous un pont, bus sur
  un pont, zone d'arrêt au bord du tablier) ; écarts SC-003 dus aux ponts documentés. Règle :
  un écart au prototype n'est pas une erreur en soi ; les relectures terrain du mainteneur
  (issues) priment sur la ressemblance au prototype.
- **Références** : issue #18, branche `002-issue-18-ouvrages`.

### LL-007 — Liens Panoramax du rapport vers une page sans photo (2026-09-29) — Close

- **Contexte** : relecture du rapport de Courbevoie par le mainteneur (fiche d'un point).
- **Symptôme** : le lien « Photo de rue du … » ouvre la page d'accueil de panoramax.fr, sans
  la photo.
- **Causes racines** :
  1. Pourquoi ? L'URL était `https://panoramax.fr/#focus=pic&pic=<id>` : panoramax.fr est le
     site vitrine du projet, pas une visionneuse ; il ignore ces paramètres.
  2. Pourquoi ce format ? Écrit par analogie avec les paramètres de la visionneuse, sans
     ouvrir une seule fois le lien produit.
  3. Pourquoi non détecté ? Les tests vérifiaient la présence d'un lien, pas sa cible ; les
     fixtures figées reproduisaient la même URL.
- **Correctif** : visionneuse du méta-catalogue `https://api.panoramax.xyz/#focus=pic&pic=<id>`
  (vérifiée dans un navigateur : la photo s'affiche) ; 65 URL des fixtures réécrites.
- **Mesure préventive** : test du format exact des liens (`tests/rapport/test_rendu.py`) ;
  règle : tout lien externe généré est ouvert au moins une fois dans un navigateur avant sa
  PR (même esprit que LL-003 : vérifier l'effet, pas seulement la forme).
- **Références** : branche `002-us3-us4-rapport-couts`.

### LL-006 — Port de la base locale réservé par Windows (2026-09-29) — Close

- **Contexte** : développement sous WSL2 avec Docker Desktop, reprise après redémarrage du
  poste, branche `002-us2-antibot-quotas`.
- **Symptôme** : `docker compose up -d db` échoue : `ports are not available: exposing port
  TCP 127.0.0.1:55432 … /forwards/expose returned unexpected status: 500`.
- **Causes racines** :
  1. Pourquoi l'échec ? Le port 55432 est dans une plage réservée par Windows
     (`netsh int ipv4 show excludedportrange protocol=tcp` : 55334–55433).
  2. Pourquoi réservée ? WinNAT/Hyper-V réserve des blocs de ports au démarrage, pris dans la
     plage dynamique (49152–65535), différents à chaque redémarrage.
  3. Pourquoi y était-on ? Les ports de `compose.yaml` (55432, 55000) avaient été choisis
     « hauts » pour éviter les conflits, sans tenir compte de la plage dynamique.
- **Correctif** : ports locaux déplacés hors de la plage dynamique (base 15432, S3 simulé
  15000) et rendus configurables : `BITUMAP_DB_PORT` et `BITUMAP_S3_PORT` dans `.env`, lus par
  `compose.yaml` et `tests/conftest.py` (aucun port en dur, revue de la PR #16).
- **Mesure préventive** : règle : tout port publié sur le poste est choisi sous 49152 ;
  en cas d'échec d'exposition, vérifier d'abord `excludedportrange`.
- **Références** : branche `002-us2-antibot-quotas`.

### LL-005 — Python local sans module bz2 (2026-09-28) — Close

- **Contexte** : développement, premiers tests utilisant le stockage objet simulé (moto).
- **Symptôme** : `ModuleNotFoundError: No module named '_bz2'` à l'import de moto.
- **Causes racines** :
  1. Pourquoi ? Le Python 3.14 du poste (`/usr/local/bin/python3`) a été compilé sans la
     bibliothèque bzip2.
  2. Pourquoi l'utilisait-on ? `uv` prend par défaut le premier Python trouvé sur le système ;
     rien n'imposait une version complète et identique pour tous.
- **Correctif** : fichier `.python-version` (3.14) et Python géré par uv
  (`uv python install 3.14`, `UV_PYTHON_PREFERENCE=only-managed uv sync`).
- **Mesure préventive** : `.python-version` versionné ; la CI (setup-python) et les images
  (Chainguard) utilisent déjà un Python complet ; procédure notée dans le README
  (section Développement).
- **Références** : branche `002-on-demand-report`.

### LL-004 — Un secret sur une branche bloquait toutes les PR (2026-09-28) — Close

- **Contexte** : CI, validation SC-001 avec 5 PR pièges (#6 à #10).
- **Symptôme** : le contrôle `secrets` échoue sur les 5 PR, alors que seule la #6 contient
  un secret.
- **Causes racines** :
  1. Pourquoi les autres PR échouent ? Gitleaks y trouve le secret de la branche
     `trap/secret`.
  2. Pourquoi le voit-il ? `actions/checkout` avec `fetch-depth: 0` récupère toutes les
     branches, et `gitleaks git` analyse par défaut `git log --all`.
  3. Pourquoi ce choix ? La spec (FR-003) demandait l'analyse de l'historique, sans préciser
     la portée par événement.
- **Correctif** : sur `pull_request`, Gitleaks n'analyse que `base.sha..head.sha` ; sur
  `main`, en hebdomadaire et à la demande, il garde l'historique complet de toutes les
  branches. Un secret poussé n'importe où reste détecté au plus tard sous 7 jours.
- **Mesure préventive** : test de portée (branche propre → 0, branche fautive → 1,
  historique complet → 1) documenté dans la PR ; comportement décrit dans
  `research.md` (R4) et `contracts/required-checks.md`.
- **Références** : PR #6 à #10 (fermées), branche `fix/gitleaks-pr-scope`.

### LL-003 — Rapports SARIF jamais publiés malgré des contrôles verts (2026-09-28) — Close

- **Contexte** : CI, première exécution de `security.yml` sur la PR #5.
- **Symptôme** : les 8 contrôles sont verts, mais Security → Code scanning ne contient que
  CodeQL ; les rapports Gitleaks, Trivy et zizmor n'ont pas été publiés, sans aucune erreur.
- **Causes racines** :
  1. Pourquoi pas publiés ? L'étape d'envoi était sautée : sa condition était fausse.
  2. Pourquoi fausse ? `hashFiles()` ne lit que l'espace de travail (`GITHUB_WORKSPACE`) ; les
     rapports étaient écrits dans `runner.temp`, donc `hashFiles` renvoyait toujours ''.
  3. Pourquoi écrits hors de l'espace de travail ? Le dépôt est monté en lecture seule dans
     les conteneurs de scan (choix de sécurité volontaire).
  4. Pourquoi non détecté en local ? actionlint et zizmor valident la syntaxe, pas la
     sémantique de `hashFiles` ; et un saut d'étape n'est pas un échec.
- **Correctif** : étape explicite `[ -s "$RUNNER_TEMP/<outil>.sarif" ]` exposant une sortie
  `present`, condition d'envoi sur cette sortie.
- **Mesure préventive** : le quickstart (§2) exige de vérifier, après chaque première
  exécution, que chaque outil apparaît dans la liste des analyses Code scanning
  (`gh api repos/aboigues/bitumap/code-scanning/analyses`). Règle générale : un contrôle
  vert ne prouve pas qu'il a produit son effet ; vérifier la sortie attendue.
- **Références** : PR #5.

### LL-002 — kDrive recrée les fichiers retirés par git (2026-09-28) — Close

- **Contexte** : développement, dépôt cloné dans un dossier synchronisé par kDrive,
  passage de la branche `001-security-ci-baseline` à `main`.
- **Symptôme** : les fichiers de `specs/001-security-ci-baseline/` réapparaissent (avec des fins
  de ligne CRLF) sur une branche où ils n'existent pas, et sont commités par erreur dans
  `chore/scaleway-bootstrap` ; supprimés, ils reviennent en moins de 20 s.
- **Causes racines** :
  1. Pourquoi réapparaissent-ils ? Le client kDrive interprète la suppression faite par
     `git switch` comme une divergence et restaure sa copie en ligne.
  2. Pourquoi a-t-on commité ? `git add -A` prend tout ce qui est non suivi, sans relecture de
     la liste avant le commit.
  3. Pourquoi le dépôt est-il dans kDrive ? Emplacement historique du dossier de travail ; la
     sauvegarde est en réalité assurée par GitHub.
- **Correctif** : fichiers retirés de la branche par un commit dédié (sans force-push,
  principe IX).
- **Mesure préventive** : le dossier du dépôt est **exclu de la synchronisation kDrive**
  (exclusion suivie d'un redémarrage de kDrive et de la fermeture des fichiers ouverts, sans
  quoi elle n'est pas appliquée). Vérifié par un aller-retour de branches sans recréation
  après 45 s. Toujours : n'ajouter que des chemins explicites (jamais `git add -A`) et relire
  `git status` avant chaque commit. Tout nouveau poste de travail : cloner hors de tout
  dossier synchronisé (OneDrive, kDrive, Dropbox…).
- **Références** : branche `chore/scaleway-bootstrap`, commit « fix: retirer les fichiers de la
  001 recréés par la synchronisation kDrive ».

### LL-001 — Arrêt silencieux du bootstrap Scaleway en relance (2026-09-28) — Close

- **Contexte** : développement, première relance de `infra/bootstrap/bootstrap.sh` pour
  vérifier son idempotence.
- **Symptôme** : la relance s'arrête après l'étape 3, sans message ni sortie JSON ; l'étape
  « bucket d'état » n'est pas exécutée.
- **Causes racines** :
  1. Pourquoi l'arrêt ? `jq` échoue (`startswith() requires string inputs`) et `set -e` +
     `pipefail` stoppent le script.
  2. Pourquoi `jq` échoue ? `scw object bucket list -o json` renvoie la clé `Name` (majuscule,
     format S3) et non `name` comme les autres commandes `scw`.
  3. Pourquoi ne l'a-t-on pas vu ? La première exécution crée le bucket sans passer par ce
     filtre (liste vide) ; seule la relance lit la liste.
  4. Pourquoi aucun message ? L'erreur `jq` était redirigée (`2>/dev/null`) et le script
     n'avait pas de piège `ERR`.
- **Correctif** : filtre `(.Name // .name)` ; piège `trap … ERR` + `errtrace` qui affiche la
  ligne et la commande en échec.
- **Mesure préventive** : tout script d'infrastructure DOIT avoir un piège `ERR` et être
  exécuté **deux fois** avant sa PR (idempotence), ce qui est désormais noté dans
  `infra/bootstrap/README.md`. Aucun doublon n'avait été créé : l'arrêt est survenu avant la
  création.
- **Références** : branche `chore/scaleway-bootstrap`.
