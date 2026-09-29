# Contrat : projection été par été (007)

Complète [le contrat de 002](../../002-on-demand-report/contracts/http-api.md) : mêmes
en-têtes, session obligatoire (`401` sinon), erreurs `{ "erreur", "message" }`. Aucune
requête ne modifie de données (pas de `csrf`).

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /projection/{insee}/{empreinte}` | `frequentation` (−5 à 10, en % par an, 0 par défaut) | page : en-tête (rapport, version de projection, hypothèse, seuil) ; description des trois scénarios (été de référence, degrés-jours, jours ≥ 35 °C) ; **points à traiter** par scénario et par été ; tableau de tous les points (été du seuil par scénario) ; mention « indice relatif, pas de millimètres » | `400 hypothese_invalide`, `404` |
| `GET /projection/{insee}/{empreinte}/points/{point_id}` | `frequentation` | fiche : trois courbes (SVG), ligne du seuil, été de franchissement par scénario, facteurs (score initial, sensibilité à la chaleur, charge, âge de l'enrobé et sa source) | `404` |
| `GET /projection/{insee}/{empreinte}/projection.csv` | `frequentation` | UTF-8 avec BOM, `;` : une ligne par point et par scénario : point, désignation, niveau, score initial, score par été, été du seuil, hypothèse, version, seuil | `400`, `404` |

Le rapport de 002 gagne un lien « Projection été par été » vers la première page.

Page et fiche : aucun script (courbes en SVG produit par le serveur) ; CSP de 002.
