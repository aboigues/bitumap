# Modèle de données : Méthode v2 (004)

Pas de nouvelle table de base : la v2 change le calcul et le contenu du rapport. Les sources
nouvelles sont mises en cache dans le bucket de cache de 002.

## Point (rapport) — champs ajoutés ou modifiés

| Champ | Règles |
|---|---|
| `facteurs[ensoleillement]` | `valeur` = heures de soleil moyennes juin–août ; `details` : `cause_ombre` (`batiment`, `arbre`, `ouvrage`, `relief`), `source` (`lidar_hd` ou `repli_1.2`), `millesime_lidar` |
| `facteurs[chaleur_*]` | un facteur par indicateur **retenu** (FR-006) : `temperature_surface` (°C, été de référence), `mineralisation` (%), `contexte_urbain` (zone climatique) ; les climatiseurs sont écartés de la 2.0 (research R4) ; `statut` `non_evalue` si donnée absente |
| `facteurs[poids_lourds]` | `valeur` = poids lourds par jour ; `details` : `source`, `annee`, `troncon` ; ×1,0 et `non_evalue` sans comptage |
| `niveau_v1` | groupe du point en méthode 1.2 (`P1a` … `P3`) |
| `raison_changement` | facteur dont l'effet a le plus varié, si le niveau change ; sinon nul |

Les facteurs de 1.x (charge, sollicitation, site, âge de l'enrobé, type de route affiché)
sont conservés.

## Rapport — champs ajoutés

| Champ | Règles |
|---|---|
| `ete_reference` | année de l'été dont proviennent température de surface et canicules ; jours de forte chaleur de cet été |
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
