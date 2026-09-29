# Quickstart : valider la projection été par été (007)

Contrat : [contracts/http-api.md](contracts/http-api.md) ; données :
[data-model.md](data-model.md) ; décisions : [research.md](research.md).

## 1. Prérequis

- Environnement de 002 et rapport de Courbevoie produit localement.
- Étés figés dans les fixtures (sévérités de Paris-Montsouris 2016–2026, R2) : tests sans
  réseau.
- `uv run pytest tests/projection`.

## 2. Vérifications

| Vérification | Attendu |
|---|---|
| Sévérités figées | 2016–2025 : 49,8 degrés-jours en moyenne ; 2022 : 78,5 ; 2026 : 196,3 |
| « Paix - Verdun » (A23742), très chaud | seuil de 95 atteint dès le premier été (SC-002) |
| Monotonie | pour 100 % des points, été du seuil jamais plus tardif en « chaud » qu'en « moyen », ni en « très chaud » qu'en « chaud », ni avec +5 % de fréquentation qu'à fréquentation stable (SC-003) |
| Reproductibilité | deux calculs identiques au point près (SC-004) |
| Point sans chaleur évaluée | sensibilité 1, marqué « chaleur non évaluée » |
| Réfection postérieure (relevé 003 simulé) | le score repart à l'été suivant la réfection |
| Horizon dépassé | « pas avant 2032 », jamais de date extrapolée |
| Présentation | aucune valeur en millimètres ; « indice relatif » affiché (SC-005) |
| Export | CSV lisible dans un tableur, hypothèse et version présentes |

## 3. Parcours utilisateur

- Depuis le rapport de Courbevoie, ouvrir « Projection été par été » : lire les points à
  traiter avant l'été 2027 dans chaque scénario, en moins de 2 minutes (SC-001).
- Passer la fréquentation à +5 % par an : des points atteignent le seuil plus tôt, aucun plus
  tard.

## 4. Suivi (après 003)

- À la première campagne de relevés répétés : vérifier que les points dont l'orniérage
  s'aggrave sont plus souvent en tête de projection (SC-006) ; recaler `k` et le seuil si
  besoin (nouvelle version de projection).
