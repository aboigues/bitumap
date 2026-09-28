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

### LL-002 — kDrive recrée les fichiers retirés par git (2026-09-28) — Ouverte

- **Contexte** : développement, dépôt cloné dans un dossier synchronisé par kDrive
  (`C:\Users\PC\kDrive\...`), passage de la branche `001-security-ci-baseline` à `main`.
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
- **Mesure préventive** : déplacer le dépôt hors de tout dossier synchronisé (système de
  fichiers WSL, ex. `~/dev/bitumap`) ; d'ici là, n'ajouter que des chemins explicites
  (jamais `git add -A`) et relire `git status` avant chaque commit. La leçon sera close une
  fois le dépôt déplacé.
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
