# Quickstart : valider le parcours de surveillance (006)

Contrat : [contracts/http-api.md](contracts/http-api.md) ; données :
[data-model.md](data-model.md) ; décisions : [research.md](research.md).

## 1. Prérequis

- Environnement de 002 et un rapport de Courbevoie produit localement.
- Tests automatiques sans réseau (géocodage et itinéraire simulés) :
  `uv run pytest tests/parcours`.
- Validation réelle (§ 3) : accès réseau à `data.geopf.fr`.

## 2. Tests automatiques

| Vérification | Attendu |
|---|---|
| Ordre du rang | les points visités sont dans l'ordre croissant du rang (SC-003) |
| Durée | la durée estimée (trajets, arrêts, retour) ne dépasse jamais la durée maximale (SC-003) |
| Point trop loin | sauté, listé « non visité (durée) », le suivant est essayé |
| Plus de 15 intermédiaires | tracé en plusieurs tronçons enchaînés, sans trou |
| GPX | conforme au schéma GPX 1.1 ; points nommés « ordre · niveau · désignation » ; aucune adresse e-mail |
| Service en erreur | `503`, aucun GPX |
| Accès | un autre compte obtient `404` sur le résultat et le GPX |
| Expiration | parcours de plus de 24 h purgé (SC-006) |

## 3. Parcours réel (Courbevoie)

- Départ « 2 place de l'hôtel de ville, Courbevoie » ; niveaux Critique et Sérieux
  (21 points) ; voiture ; 3 h ; arrêt 5 min.
- Attendu : résultat en moins de 30 s (SC-001) ; boucle sur la carte ; feuille de route sur
  une page A4 ; non visités listés s'il y en a.
- Télécharger le GPX et l'ouvrir dans deux applications de navigation et un GPS de randonnée
  (SC-002).
- Même chose « à pied », 2 h : durées de marche, moins de points.
- Sur 3 tournées réelles : comparer la durée effective à la durée estimée (SC-007, ±20 %).
