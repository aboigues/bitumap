# Modèle de données : progression de la génération (009)

## Demande (table `demande`, existante) — colonnes ajoutées

Migration `src/bitumap/db/migrations/006_avancement.sql`.

| Colonne | Type | Contrainte | Sens |
|---|---|---|---|
| `avancement` | `smallint` | `NULL` ou `0 ≤ avancement ≤ 99` | pourcentage de la génération en cours ; jamais 100 (FR-004) |
| `fin_estimee` | `timestamptz` | `NULL` permis | fin estimée, en heure absolue ; renseignée pendant la phase `ia` seulement (R5) |

Contrainte de `etape` élargie : `etape IN ('acquisition', 'calcul', 'sources', 'points',
'ia', 'rapport')`. Les valeurs `acquisition` et `calcul` ne sont plus écrites ; elles
restent admises pour les lignes déjà en base.

## Transitions

| Événement (code) | `etat` | `etape` | `avancement` | `fin_estimee` |
|---|---|---|---|---|
| prise en charge (`prise_en_charge.prendre`) | `en_cours` | `NULL` | `NULL` (affiché « démarrage ») | `NULL` |
| avancement du calcul (`prise_en_charge.avancer`, nouveau) | `en_cours` | phase courante | `GREATEST(ancien, nouveau)` | estimée en phase `ia`, `NULL` sinon |
| fin (`terminer`) | `terminee` | `NULL` | `NULL` | `NULL` |
| échec (`echouer`) | `en_echec` | `NULL` | `NULL` | `NULL` |
| remise en file (reprise, report) | `en_file` | `NULL` | `NULL` | `NULL` |

Règles :

- `avancer` n'écrit que si `etat = 'en_cours'` (aucune écriture sur une demande remise en
  file ou terminée entre-temps).
- `avancement` ne décroît jamais pendant une même prise en charge (`GREATEST`) ; il est
  remis à `NULL` à chaque sortie de l'état `en_cours`.
- Aucune autre donnée n'est exposée (FR-009) : ni identifiant de point, ni coût, ni erreur.

## Phases (valeurs de `etape` écrites par le job)

| `etape` | Libellé affiché | Bornes du pourcentage |
|---|---|---|
| `NULL` | démarrage | — |
| `sources` | lecture des données | 0 → 5 |
| `points` | analyse des points | 5 → 20 |
| `ia` | analyse des photos aériennes | 20 → 97 |
| `rapport` | mise en forme du rapport | 97 → 99 |

Détail du calcul : [contracts/progression.md](contracts/progression.md).
