# Contrats : méthode v2 (004)

## 1. Rapport (modifie `specs/002-on-demand-report/contracts/report-bundle.md`)

Champs ajoutés au point et au rapport : [data-model.md](../data-model.md). Affichage :

- **Fiche** : ensoleillement (heures juin–août, cause principale d'ombre, source) ; un facteur
  par indicateur de chaleur retenu, avec l'été de référence ; poids lourds (valeur, source,
  année) ou « non évalué (aucun comptage publié) » ; si le niveau a changé : « v1 : Sérieux —
  raison : chaleur, minéralisation forte ».
- **Synthèse** : été de référence et jours de forte chaleur ; part des points couverts par un
  comptage de poids lourds ; tableau niveau v1 × niveau v2.
- **Méthode** : version 2.0, facteurs et bornes, indicateurs écartés et pourquoi, sources
  (dont la source hors UE déclarée).

## 2. Outil d'évaluation (mainteneur, hors service)

```text
uv run python -m bitumap.methode.evaluer \
    --releves <export des relevés de 003, GeoJSON ou CSV> \
    --communes 92026 92004 … \
    [--sortie evaluation-v2.md]
```

Entrées : export des relevés de 003 (`releves.geojson`, contrat de 003) ; communes de
référence (≥ 3). Refus explicite si moins de 100 points relevés.

Sortie (Markdown) :

| Section | Contenu |
|---|---|
| Référence | nombre de points relevés et orniérés par commune |
| SC-001 | part des orniérés dans Critique + Sérieux + Important : v1, v2, écart (objectif ≥ +10 points) |
| Indicateurs | pour chaque candidat : mesure avec et sans, écart global et par commune, décision (retenu si ≥ +2 points et aucune commune dégradée), raison |
| Ensoleillement (SC-002) | points observés, écart moyen calculé / observé (objectif < 1,5 h) |
| Changements de niveau | tableau v1 × v2 par commune |
| Décision | recommandation de mise en service (à confirmer par le mainteneur) |

## 3. Configuration (ajouts à `contracts/configuration.md` de 002)

| Variable | Défaut | Rôle |
|---|---|---|
| `BITUMAP_METHODE` | `1.2` | version appliquée aux nouveaux rapports ; passe à `2.0` à la mise en service |
| `BITUMAP_ETE_REFERENCE` | dernier été disponible | été des indicateurs annuels |
| `BITUMAP_STATION_METEO` | station de référence de l'agglomération | canicules, partagée avec 007 |
