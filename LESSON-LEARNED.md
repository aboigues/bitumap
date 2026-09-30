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

### LL-016 — Ombres fictives du LiDAR malgré des tests verts (2026-09-30) — Close

- **Contexte** : développement de 004 (US1, ensoleillement sur LiDAR HD), première exécution
  de la méthode 2.0 sur les données figées de Courbevoie, avant la PR.
- **Symptôme** : tous les tests (grilles synthétiques) passaient, mais sur Courbevoie des
  carrefours passaient de 10 h à 1,3 h de soleil, « à cause de bâtiments » absents de la
  BD TOPO ; la cause « arbre » ne sortait que 6 fois sur 154 points.
- **Causes racines** :
  1. Pourquoi ? Le MNS contient tout ce que le laser a touché : véhicules présents lors du
     survol (2 à 3 m au bord des points de mesure), mâts de feux et lampadaires (8 à 16 m à
     2 m des feux) ; à 2 m, un tel objet cache le soleil jusqu'à 57° de hauteur.
  2. Pourquoi « arbre » si rare ? L'infrarouge manque les arbres à l'ombre des immeubles
     (avenue Gambetta) et le bord des toits tombe à 1 m hors de l'emprise BD TOPO.
  3. Pourquoi non vu par les tests ? Les grilles synthétiques ne contenaient que ce que
     l'on y mettait : des bâtiments et des arbres idéaux (même famille que LL-003 :
     vérifier l'effet sur les données réelles, pas seulement la forme).
- **Correctif** : ouverture morphologique du sursol (objets de moins de 3 m de large
  effacés), sursol de moins de 4 m ramené au sol, cause « arbre » par la végétation à 1 m
  près ou la rugosité du sursol (5 × 5 m), emprises BD TOPO élargies d'un mètre pour le
  classement. Chaque cas vérifié sur l'orthophoto et l'ombrage du MNH.
- **Mesure préventive** : tests `test_vehicule_du_survol_ignore`, `test_mat_de_feu_ignore`,
  `test_houppier_rugueux_classe_arbre_sans_infrarouge`,
  `test_construction_lisse_non_repertoriee_classe_batiment` ;
  `tests/non_regression/test_courbevoie_v2.py` sur les données figées réelles. Règle : toute
  nouvelle source mesurée est passée sur une commune réelle et ses plus grands écarts sont
  examinés sur image avant la PR.
- **Références** : branche `004-us1-ensoleillement-lidar`.

### LL-015 — Hook de protection de main inactif hors de /mnt/c (2026-09-30) — Close

- **Contexte** : préparation du déplacement du dépôt de `/mnt/c` (disque Windows, dossier
  kDrive exclu) vers le disque natif de WSL ; inventaire avant migration.
- **Symptôme** (prévisible, non observé en usage) : les 21 fichiers versionnés commençant par
  `#!`, dont `.claude/hooks/guard-main.sh`, étaient en mode `100644`. Rejoué depuis le disque
  natif, le hook répond `permission denied` (code 126) ; Claude Code traite ce code comme une
  erreur non bloquante : un `git push origin main` n'aurait plus été refusé par le hook.
- **Causes racines** :
  1. Pourquoi ? Le bit d'exécution n'a jamais été enregistré dans git pour ces scripts.
  2. Pourquoi non vu ? Sous `/mnt/c`, WSL présente tous les fichiers en `rwxrwxrwx` et
     `core.filemode` vaut `false` : les scripts s'exécutaient et git ne voyait aucun écart.
  3. Pourquoi aucun contrôle ? Aucun test ne vérifiait le mode des scripts ; les interdictions
     de `.claude/settings.json` (push sur main, fusion de PR) masquaient en partie l'absence
     du hook.
- **Correctif** : `git update-index --chmod=+x` sur les 21 fichiers commençant par `#!`.
- **Mesure préventive** : test `tests/unit/test_scripts_executables.py` (tout fichier suivi
  commençant par `#!` est en `100755`, et le hook de protection de main en particulier),
  exécuté en CI sur un système de fichiers Linux. Règle : un script ajouté sous `/mnt/c`
  passe par `git update-index --chmod=+x` ; le dépôt de travail est à déplacer sur le disque
  natif de WSL.
- **Références** : branche `chore/bits-execution-scripts`.

### LL-014 — Une photo retirée pouvait être renvoyée sous le même identifiant (2026-09-30) — Close

- **Contexte** : revue de sécurité de 003 (T042), branche de la modération (US5) ; défaut
  présent depuis le MVP (#24), trouvé avant toute mise en production.
- **Symptôme** (prévisible, non observé) : après le retrait d'une photo, par son auteur ou
  par le mainteneur (RGPD), l'auteur pouvait redemander un formulaire d'envoi pour le même
  identifiant, déposer une autre image et la confirmer : la photo redevenait `visible`,
  annulant le retrait (FR-016).
- **Causes racines** :
  1. Pourquoi ? `formulaire` acceptait un identifiant existant quel que soit son état, et
     `confirmer` ne distinguait que « visible » (rejeu) du reste, traité comme une
     quarantaine.
  2. Pourquoi ? L'idempotence (réenvoi depuis un téléphone hors réseau) a été pensée pour
     deux états, `quarantaine` et `visible` ; les états de retrait, ajoutés ensuite, n'ont pas
     été rapprochés des chemins d'envoi.
  3. Pourquoi non vu ? Les tests de retrait vérifiaient l'effet du retrait, jamais une
     tentative d'envoi postérieure ; la mise à jour finale n'avait pas de garde sur l'état
     (course possible entre retrait et confirmation).
- **Correctif** : `409 photo_retiree` au formulaire et à la confirmation d'une photo
  retirée (quarantaine effacée) ; mise à jour `… AND etat = 'quarantaine'`, et, si la photo a
  été retirée entre-temps, suppression de toutes les versions de l'objet écrit. Le rejeu
  d'une photo `visible` efface aussi la quarantaine redéposée.
- **Mesure préventive** : tests `test_photo_retiree_ne_peut_etre_renvoyee` (auteur, RGPD),
  `test_retrait_pendant_l_envoi`, `test_depot_rejoue_apres_succes`. Règle : tout état
  terminal (retrait, suppression) est testé contre chaque chemin d'écriture qui pourrait le
  faire revenir en arrière, rejeux idempotents compris.
- **Références** : branche `003-us5-moderation-finition`.

### LL-013 — Original d'une photo récupérable dans le bucket versionné (2026-09-30) — Close

- **Contexte** : développement de 003 (US5, modération), relecture du retrait RGPD ; défaut
  latent, trouvé avant toute mise en production (aucune donnée réelle).
- **Symptôme** : après réencodage d'une photo, l'original déposé en `quarantaine/` (avec ses
  métadonnées EXIF, dont la position GPS) restait lisible : la clé portait encore une
  version non courante et un marqueur de suppression (vérifié par une sonde sur le S3
  simulé).
- **Causes racines** :
  1. Pourquoi ? La quarantaine était effacée par un simple `delete_object`, qui, dans un
     bucket versionné, ajoute un marqueur de suppression sans détruire le contenu.
  2. Pourquoi ce choix ? Le versionnement du bucket `bitumap-terrain` (décidé pour
     l'historique) n'a pas été rapproché de l'effacement des données personnelles.
  3. Pourquoi non vu ? Les tests vérifiaient que la clé n'était plus lisible (`lire` →
     `None`), pas qu'aucune version n'existait (même famille que LL-003 : l'effet attendu
     n'était pas mesuré).
- **Correctif** : `stockage.effacer_definitivement` supprime toutes les versions et tous les
  marqueurs d'une clé ; utilisé pour la quarantaine et pour le retrait RGPD d'une photo.
- **Mesure préventive** : tests `test_original_non_conserve_par_le_versionnement` et
  `test_retrait_rgpd_d_une_photo` (aucune version restante) ; T040 : la règle de cycle de vie
  de `quarantaine/` expire aussi les versions non courantes. Règle : dans un bucket
  versionné, tout effacement de donnée personnelle supprime toutes les versions et est
  testé sur la liste des versions.
- **Références** : branche `003-us5-moderation-finition`.

### LL-012 — Constaté absent du rapport malgré des tests verts (2026-09-29) — Close

- **Contexte** : développement de 003 (US2), essai du parcours dans un navigateur (émulation
  mobile) avant la PR.
- **Symptôme** : un relevé saisi n'apparaît ni dans la synthèse « Constaté » ni dans la fiche
  du rapport ; aucune erreur en console. Les tests de `test_rapport_releves.py` passaient.
- **Causes racines** :
  1. Pourquoi ? Le script du rapport lit le bloc `releves` au chargement et ne le trouvait
     pas : il valait `{}`.
  2. Pourquoi ? L'API insérait le bloc juste avant `</body>`, donc **après** le script en
     ligne, qui s'exécute dès qu'il est analysé.
  3. Pourquoi non vu ? Les tests vérifiaient la présence et le contenu du bloc dans le HTML,
     pas qu'il soit lisible par le script (même famille que LL-003 : présent ≠ effectif).
- **Correctif** : le bloc est inséré juste après le bloc `donnees`, avant le script.
- **Mesure préventive** : test `test_bloc_avant_le_script_qui_le_lit` (ordre des blocs) ;
  le parcours navigateur du quickstart reste obligatoire avant chaque PR touchant le rapport
  ou la saisie.
- **Références** : branche `003-terrain-releves`.

### LL-011 — CSP d'un rapport en cache liée à la version courante du script (2026-09-29) — Close

- **Contexte** : conception de 003 (relevés terrain), rapport servi par l'API de 002 ;
  défaut latent, trouvé avant toute mise en production.
- **Symptôme** (prévisible, non observé) : après toute modification de
  `rapport/interactions.js` (PR #17, #19), un rapport encore en cache (30 jours), produit
  avec l'ancien script, serait servi avec une CSP n'autorisant que l'empreinte du **nouveau**
  script : filtres, fiche et carte inertes.
- **Causes racines** :
  1. Pourquoi ? `CSP_RAPPORT` était une constante calculée au démarrage sur le script du code
     en cours, alors que le script est figé dans chaque `rapport.html` stocké.
  2. Pourquoi non vu ? Les tests génèrent le rapport et le servent avec le même code ; aucun
     test ne servait un rapport produit par une version antérieure.
  3. Pourquoi pas d'incident ? Aucun rapport n'est encore en production.
- **Correctif** : `rapport.rendu.csp_du_document(html)` calcule, à chaque service,
  l'empreinte des scripts en ligne **du document servi** (analyseur HTML, blocs de données
  JSON exclus) ; le document vient du bucket privé, écrit par le job.
- **Mesure préventive** : `tests/api/test_rapport_csp.py` (ancien script autorisé, bloc JSON
  exclu, balise en majuscules reconnue, document sans script ⇒ `script-src 'none'`). Règle :
  tout artefact stocké et servi plus tard est testé avec une version antérieure du code.
- **Références** : branche `003-terrain-releves` (T006, T007).

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
