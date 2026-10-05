# Contrat : interface HTTP du parcours de surveillance (006)

Complète [le contrat de 002](../../002-on-demand-report/contracts/http-api.md) : mêmes
en-têtes, session obligatoire (`401` sinon), jeton `csrf` sur les requêtes qui modifient,
erreurs `{ "erreur", "message" }` sans détail technique.

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /parcours/{insee}` | — | formulaire : adresse, niveaux (avec le nombre de points de chacun), mode, durée maximale, temps d'arrêt, option « exclure les points relevés depuis moins de N jours » (si 003) | `404` rapport absent |
| `GET /parcours/adresses?q=&insee=` | texte saisi | 5 propositions d'adresses officielles (libellé, position, score) | `400` texte trop court |
| `POST /parcours/{insee}` | `csrf`, `adresse` (texte, 300 caractères au plus), `choix` (indice de la proposition si l'adresse est ambiguë), `niveaux[]`, `mode`, `duree_max_min` (30–480), `arret_min` (0–30), `exclure_releves` (case), `exclusion_releves_jours` (1–365, 30 par défaut, pris en compte si la case est cochée) | `303` vers `/parcours/resultat/{id}` ; adresse ambiguë ou introuvable : formulaire `400` avec les propositions | `400 parametres_invalides`, `400 aucun_point`, `400 duree_insuffisante` (avec la durée minimale), `400 depart_trop_loin` (> 20 km), `429 quota_parcours`, `503 itineraire_indisponible` |
| `GET /parcours/resultat/{id}` | — | résumé (dont le nombre de points exclus pour relevé récent), feuille de route imprimable (A4), liste des non visités, lien de téléchargement du GPX ; pas de carte : la boucle se suit dans le GPX (décision du 2026-10-05) | `404` (inconnu, expiré ou d'un autre compte) |
| `GET /parcours/resultat/{id}.gpx` | — | `application/gpx+xml`, `Content-Disposition: attachment; filename="parcours-{insee}-{date}.gpx"` | `404` |

## GPX 1.1 (FR-008)

- `metadata` : nom « Parcours de surveillance — {commune} », date, rapport (date, méthode),
  sources et licences (IGN Géoplateforme, IDFM, OpenStreetMap) ; aucune donnée de compte.
- `wpt` : départ (« Départ »), puis un par point visité : `name` = « {ordre} · {niveau} ·
  {désignation} », `desc` = rang, identifiant du point, lien vers la fiche du rapport.
- `trk` : la boucle complète, un segment par tronçon calculé.

## Limites

20 parcours par compte et par jour ; 60 candidats évalués au plus par parcours ; résultat
conservé 24 h.
