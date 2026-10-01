# Modèle de données : Méthode v2 (004)

Pas de nouvelle table de base : la v2 change le calcul et le contenu du rapport. Les sources
nouvelles sont mises en cache dans le bucket de cache de 002.

## Point (rapport) — champs ajoutés ou modifiés

| Champ | Règles |
|---|---|
| `facteurs[ensoleillement]` | `valeur` = heures de soleil moyennes juin–août ; `details` : `cause_ombre` (`batiment`, `arbre`, `ouvrage`, `relief`), `source` (`lidar_hd` ou `repli_1.2`), `millesime_lidar` |
| `facteurs[chaleur_*]` | un facteur par indicateur **retenu** (FR-006) : `temperature_surface` (°C, été de référence), `mineralisation` (%), `contexte_urbain` (zone climatique), et l'aléa de la 1.2 (`alea`) comme référence ; non retenu ⇒ affiché, effet 1,0, `details` : `retenu`, `effet_si_retenu` (et `ete` pour la température) ; les climatiseurs sont écartés de la 2.0 (research R4) ; `statut` `non_evalue` si donnée absente |
| `facteurs[poids_lourds]` | `valeur` = poids lourds par jour hors bus, sens le plus chargé ; `details` : `source`, `annee`, `troncon`, `pl_comptes`, `bus_retires` ; ×1,0 et `non_evalue` sans comptage |
| `niveau_v1` | groupe du point en méthode 1.2 (`P1a` … `P3`) |
| `raison_changement` | facteur dont l'effet a le plus varié, si le niveau change ; sinon nul |

Les facteurs de 1.x (charge, sollicitation, site, âge de l'enrobé, type de route affiché)
sont conservés.

## Rapport — champs ajoutés

| Champ | Règles |
|---|---|
| `ete_reference` | année de l'été de référence ; station, `station_nom`, `jours_mesures`, `jours_forte_chaleur` (≥ 30 °C), `jours_tres_forte_chaleur` (≥ 35 °C), `maximum_c` ; `temperature_ete` (été de la température de surface, le précédent si repli) |
| `couverture_poids_lourds` | part des points couverts par un comptage |
| `bilan_changements` | nombre de points par (niveau v1, niveau v2) |
| `sources` | + LiDAR HD (IGN), température de surface (USGS, **hors UE, déclaré**), comptages (départements, État), données quotidiennes (Météo-France) |

## Cache des sources (bucket de cache)

| Clé | Contenu | Validité |
|---|---|---|
| `lidar/{mns|mnt}/{dalle}.tif` | dalle 1 km | millésime (stable) |
| `lst/{ete}/{insee}.tif` | médiane de la température de surface de l'été, emprise de la commune | par été |
| `comptages/{source}/{annee}.json` | tronçons comptés et poids lourds par jour | par année de publication |
| `meteo/{station}/{ete}.json` | températures quotidiennes de l'été | par été (partagé avec 007) |

## Évaluation (outil hors service)

- **Relevé de référence** : point, commune, niveau constaté (003), orniéré (booléen).
- **Résultat d'indicateur** : indicateur, mesure avec et sans, écart, décision (retenu ou
  écarté), raison ; consigné dans `docs/methode/CHANGELOG.md` à la mise en service.

## Classement corrigé par le terrain (R9, calculé au service du rapport)

Aucune table nouvelle : lecture des relevés visibles de 003 (`releve`, dernière
`releve_version`). Bloc JSON `classement-terrain` inséré par l'API dans le rapport servi
(rapports 2.0 seulement).

| Champ | Règles |
|---|---|
| `points.{id}.annee_refection` | plus récente année de réfection d'un relevé visible du point de source `constatee` ou `services_techniques` (FR-016) |
| `points.{id}.source_refection` | `constatee` ou `services_techniques` |
| `points.{id}.effet` | `min(1,0 ; 0,5 + 0,05 × n)`, `n = ete_reference − annee_refection` (≥ 0) ; 1,0 si annulé (FR-017, FR-018) |
| `points.{id}.annule` | vrai si le relevé visible le plus récent, daté d'une année ≥ `annee_refection`, constate `marque` ou `grave` (FR-018) |
| `points.{id}.rang`, `points.{id}.groupe` | rang et niveau après correction, mêmes règles que l'estimé (`score.combinaison`) |
| `nb_points_corriges` | points dont l'effet est < 1,0 |

Aucune donnée personnelle (ni auteur, ni adresse, ni photo). Seuls les points ayant une
réfection confirmée figurent dans `points`.
