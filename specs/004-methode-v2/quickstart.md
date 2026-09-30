# Quickstart : valider la méthode v2 (004)

Contrats : [contracts/methode-v2.md](contracts/methode-v2.md) ; données :
[data-model.md](data-model.md) ; décisions : [research.md](research.md).

## 1. Prérequis

- Environnement de développement de 002 ; fixtures de Courbevoie complétées par
  `tools/figer_fixtures.py` (dalles LiDAR HD, température de surface de l'été de référence,
  comptages des Hauts-de-Seine, données quotidiennes de l'été).
- Pour la validation (§ 4) : 003 en service et au moins 100 relevés dans 3 communes.

## 2. Calcul (sans réseau, fixtures)

| Vérification | Attendu |
|---|---|
| `BITUMAP_METHODE=2.0` ; générer Courbevoie | rapport v2 ; version 2.0 affichée |
| Deux générations successives | rapports identiques au point près (SC-006) |
| « Verdun - Rue Latérale » (A27418) | toujours à l'ombre du pont (cause « ouvrage »), niveau non Critique (issue #18) |
| Point sous des arbres hauts | cause « arbre », heures inférieures à la 1.2 |
| Point sur une départementale comptée | facteur poids lourds avec source et année ; voie communale : « non évalué » |
| Synthèse | été de référence, part des points couverts, tableau v1 × v2 |
| Points qui changent de niveau | 100 % avec `niveau_v1` et raison (SC-004) |
| Durée | < 2 × durée d'un rapport 1.2 (SC-005) |

## 3. Données manquantes

- Retirer une dalle LiDAR des fixtures ⇒ point concerné « ensoleillement estimé (données de
  hauteur incomplètes) », rapport produit.
- Retirer la température de surface ⇒ facteur « non évalué », rapport produit.

## 4. Validation avant mise en service (mainteneur)

```bash
uv run python -m bitumap.methode.evaluer --releves releves.geojson \
    --communes 92026 … --sortie evaluation-v2.md
```

- SC-001 : écart v2 − v1 ≥ +10 points sur la part des orniérés dans les trois niveaux
  prioritaires.
- Indicateurs retenus et écartés consignés dans `docs/methode/CHANGELOG.md` (2.0).
- SC-002 : 30 points à ensoleillement observé pendant la campagne de relevés : écart moyen
  < 1,5 h.
- Mise en service : `BITUMAP_METHODE=2.0` (décision du mainteneur).

## 5. Réfection confirmée (R9, FR-016 à FR-018)

| Vérification | Attendu |
|---|---|
| Rapport 2.0 servi ; relevé sur A36862 : réfection 2020 « constatée », niveau « absent » ; été de référence 2026 | fiche : estimé inchangé (rang 1) ; corrigé par le terrain : effet ×0,8, rang et niveau plus bas |
| Même point, réfection « estimée par l'agent » | aucun effet ; réfection affichée comme indice |
| Nouveau relevé sur ce point, daté de 2026, niveau « marqué » | effet annulé, motif « réfection sans effet : orniérage constaté après les travaux » |
| Réfection de 2015 (11 ans avant l'été de référence) | effet ×1,0 |
| Même rapport consulté deux jours différents, mêmes relevés | même classement corrigé |
| Rapport 1.2 servi | aucun bloc `classement-terrain` |
| Score estimé, `points.geojson` et empreinte du rapport | inchangés par les relevés (principe VI) |
