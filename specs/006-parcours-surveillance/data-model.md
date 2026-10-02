# Modèle de données : Parcours de surveillance (006)

Une table éphémère dans la base de 002 (migration `006_parcours.sql`) ; rien d'autre n'est
conservé.

## parcours

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | clé ; adresse de consultation et de téléchargement |
| `compte_id` | uuid | → compte, `ON DELETE CASCADE` ; seul ce compte y accède |
| `commune_insee`, `empreinte` | texte | rapport utilisé ; date du rapport affichée |
| `depart_libelle` | texte | adresse retenue (libellé officiel) |
| `depart_lon`, `depart_lat` | réels | |
| `niveaux` | liste | parmi `P1a` … `P3` ; au moins un |
| `mode` | énuméré | `voiture`, `pied` |
| `duree_max_min` | entier | 30 à 480, 180 par défaut |
| `arret_min` | entier | 0 à 30, 5 par défaut |
| `exclusion_releves_jours` | entier, nul | US4 (003) |
| `resultat` | JSON | voir ci-dessous |
| `cree_le` | horodatage | |
| `expire_le` | horodatage | `cree_le + 24 h` ; purgé au début de chaque lot (SC-006) |

## Résultat (JSON)

- `visites` : liste ordonnée `{ordre, point_id, rang, niveau, designation, lon, lat,
  duree_cumulee_s, distance_cumulee_m, accessible}` ;
- `non_visites` : `{point_id, rang, niveau, raison}` avec `raison` ∈ `duree`, `inaccessible`,
  `releve_recent`, `limite_candidats` ;
- `trace` : géométrie de la boucle (WGS 84) ;
- `resume` : distance totale, durée (trajets, arrêts, retour), durée restante, nombre de
  points visités et non visités, date du rapport, sources.

## Données existantes réutilisées

- Points du rapport en vigueur (`points.geojson` de 002) : rang, groupe, désignation,
  position.
- `compteur_quota` : `parcours:compte:{id}:{jour}` (20).
- Relevés de 003 (US4) : date du dernier relevé visible par point.
