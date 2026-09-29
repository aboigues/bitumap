# Modèle de données : Projection été par été (007)

Aucune table : la projection est calculée à la demande (R5).

## Été (cache, partagé avec 004)

| Champ | Règles |
|---|---|
| `annee` | été (juin à août) |
| `station` | `75114001` (Paris-Montsouris) par défaut |
| `jours_30`, `jours_35` | nombre de jours avec TX ≥ 30 °C, ≥ 35 °C |
| `degres_jours_30` | somme de `max(0, TX − 30)` |
| `complet` | 92 jours renseignés |
| `source`, `extrait_le` | fichier Météo-France et date |

Clé de cache : `meteo/{station}/etes.json` (bucket de cache) ; rafraîchi une fois par an,
après la publication de l'été.

## Scénario

| Champ | Règles |
|---|---|
| `nom` | `moyen`, `chaud`, `tres_chaud` |
| `ete_reference` | `2016–2025` (moyenne), `2022`, `2026` (réglables) |
| `degres_jours`, `jours_35` | de l'été de référence |
| `rapport_r` | degrés-jours / degrés-jours du scénario moyen |

## Projection (calculée)

| Champ | Règles |
|---|---|
| `rapport` | commune, empreinte, date, méthode du score |
| `version_projection` | `1.0` |
| `hypothese_frequentation` | `g`, de −5 % à +10 % par an, 0 par défaut |
| `horizon` | 5 étés (réglable) |
| `seuil` | 95 (réglable), justification |

## Trajectoire (par point et par scénario)

| Champ | Règles |
|---|---|
| `point_id`, `designation`, `niveau` | du rapport |
| `score_initial` | score du rapport |
| `sensibilite_chaleur` | `h_p` (R3) |
| `scores` | score projeté pour chaque été de l'horizon |
| `ete_seuil` | premier été où le score atteint le seuil, ou `null` (« pas avant … ») |
| `age_enrobe` | année et source (IA « à confirmer », relevé 003) ou « inconnu » |
| `refection` | année de réfection postérieure au rapport (003), s'il y en a une |
