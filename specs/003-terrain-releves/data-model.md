# Modèle de données : Relevés terrain (003)

Tables ajoutées à la base PostgreSQL de 002 (migration `003_releves.sql`) ; fichiers photo
dans le bucket privé et versionné `bitumap-terrain`. Rien n'est jamais mis à jour en place
pour le contenu d'un relevé : toute correction ajoute une version (FR-011). Positions en
deux colonnes numériques (pas de dépendance à PostGIS, non vérifié sur Serverless SQL).

## releve

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | clé ; **généré sur le téléphone** : l'envoi est idempotent (R3) |
| `commune_insee` | texte | commune du point |
| `point_id` | texte | identifiant stable du point (002 FR-016), par exemple `A23742` |
| `point_nom`, `point_designation` | texte | copiés à la saisie (R7) |
| `niveau_estime` | texte | groupe du point à la saisie (`P1a` … `P3`) |
| `compte_id` | uuid, **nul** | → compte, `ON DELETE SET NULL` (auteur supprimé, FR-017) |
| `cree_le` | horodatage | date et heure de la saisie sur le téléphone |
| `recu_le` | horodatage | réception par le serveur |
| `lon`, `lat` | réels, nuls | position du téléphone à la validation (R9), WGS 84 |
| `distance_point_m` | réel, nul | écart à la position du point ; > 100 m ⇒ « position éloignée » |
| `retire_le`, `retire_par`, `motif_retrait` | nul | retrait (auteur : « erreur » ; mainteneur : « RGPD ») |

Index : `(commune_insee, point_id, cree_le DESC)`.

## releve_version

| Champ | Type | Règles |
|---|---|---|
| `releve_id` | uuid | → releve |
| `version` | entier | 1, 2, … ; clé `(releve_id, version)` |
| `cree_le` | horodatage | |
| `niveau` | énuméré | **obligatoire** : `absent`, `leger`, `marque`, `grave` (FR-005) |
| `profondeur_mm` | entier, nul | 0 à 200 |
| `instrument` | texte, nul | par exemple « règle et cale », « jauge » ; requis si `profondeur_mm` |
| `observation` | texte, nul | 1 000 caractères au plus |
| `annee_refection` | entier, nul | 1950 à l'année en cours |
| `source_refection` | énuméré, nul | `constatee`, `services_techniques`, `estimee_agent` ; requis si année |

La version affichée est la plus grande ; l'historique montre toutes les versions.

## photo

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | clé, généré sur le téléphone |
| `releve_id` | uuid | → releve ; 5 photos visibles au plus par relevé (FR-003) |
| `cle_objet` | texte | `communes/{insee}/points/{point_id}/{releve_id}/{photo_id}.jpg` |
| `etat` | énuméré | `quarantaine` → `visible` ; `retiree_auteur`, `retiree_mainteneur` |
| `octets` | entier | après réencodage ; somme globale ≤ plafond (R8) |
| `largeur`, `hauteur` | entier | |
| `lon`, `lat` | réels, nuls | position de prise de vue (conservée, FR-003), WGS 84 |
| `prise_le` | horodatage, nul | |
| `cree_le` | horodatage | |

Transitions : `quarantaine` → `visible` (contrôle et réencodage réussis) ; échec ⇒ ligne et
objet supprimés. `visible` → `retiree_auteur` | `retiree_mainteneur`. Pour un retrait RGPD, **toutes les
versions** de l'objet sont supprimées du bucket (sinon le versionnement garderait la photo
récupérable) ; la ligne reste comme trace, sans fichier. Un retrait par l'auteur masque la
photo et garde le fichier (historique, FR-012).

## Données existantes réutilisées (002)

- `compte` : auteur ; le **mainteneur** est le compte dont l'adresse est
  `BITUMAP_EMAIL_MAINTENEUR` (R5).
- `compteur_quota` : nouvelles clés `releve:compte:{id}:{jour}` (200),
  `photo:compte:{id}:{jour}` (1 000), `photo:formulaire:compte:{id}:{heure}` (demandes de
  formulaire d'envoi) ; `alerte_envoyee` : `stockage_photos:{jour}`.

## Vues calculées (non stockées)

- **Dernier relevé visible par point** : pour la fiche, les marqueurs et les filtres.
- **Synthèse estimé × constaté** : pour chaque niveau estimé (`P1a` … `P3`), nombre de
  points relevés par niveau constaté (FR-009).

## Pseudonyme d'auteur (R6)

`agent XXXX · domaine` : `XXXX` = 4 premiers caractères hexadécimaux d'une empreinte HMAC
de l'identifiant du compte (clé : secret `bitumap-sel-origine` de 002, dérivé à part) ;
`domaine` = partie après `@` de l'adresse. Calculé à l'affichage, jamais stocké.
