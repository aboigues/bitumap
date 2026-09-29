# Recherche : Parcours de surveillance (006)

Services testés en direct le 2026-09-29.

## R1. Adresse de départ : géocodage de la Géoplateforme

- **Décision** : service de géocodage de la Géoplateforme (IGN, Base Adresse Nationale,
  Licence Ouverte) : `https://data.geopf.fr/geocodage/search` ; testé : « 2 place de l'hôtel
  de ville Courbevoie » ⇒ « 2 Place De L'Hôtel De Ville 92400 Courbevoie », score 0,96.
  Au-dessous d'un score de 0,7 ou avec plusieurs résultats proches, l'agent choisit parmi
  5 propositions (FR-003).
- **Raison** : même fournisseur que l'itinéraire, hébergé en France, sans clé.
- **Alternative** : `api-adresse.data.gouv.fr` (répond encore) ; écartée au profit du service
  de la Géoplateforme, même origine de données.

## R2. Itinéraire : API de la Géoplateforme, 15 points intermédiaires au plus

- **Constat** (testé) : `https://data.geopf.fr/navigation/itineraire`, ressource
  `bdtopo-osrm`, profils `car` et `pedestrian` ; réponse : distance, durée, géométrie et une
  **portion par étape** ; **au plus 15 points intermédiaires par requête** (erreur explicite
  au-delà, pour `bdtopo-osrm` comme `bdtopo-valhalla`) ; 5 requêtes par seconde et par
  adresse IP ([documentation](https://geoservices.ign.fr/services-geoplateforme-itineraire)).
  Pas de service de matrice de durées.
- **Décision** : tracé final découpé en **tronçons enchaînés** de 15 intermédiaires au plus
  (fin d'un tronçon = début du suivant) ; profil `car` ou `pedestrian`.

## R3. Sélection des points dans la durée (ordre du rang)

- **Décision** : parcours des candidats dans l'ordre du rang ; pour chacun, durée
  `dernier point retenu → candidat` + arrêt + `candidat → départ` (retour, mis en mémoire
  par candidat) ; retenu si le total reste dans la durée maximale, sinon « non visité » et
  candidat suivant (FR-006).
- **Économie d'appels** : borne inférieure à vol d'oiseau (distance / vitesse maximale du
  mode) : un candidat qui ne peut pas tenir même à vol d'oiseau est écarté sans appel ;
  arrêt dès que le reste de la durée est inférieur au temps d'arrêt ; 60 candidats évalués
  au plus (les suivants sont « non visités »).
- **Coût** : pour 20 à 30 points, environ 2 appels par candidat, soit une à deux dizaines de
  secondes à 5 requêtes par seconde (SC-001 : < 30 s).
- **Alternative écartée** : un seul appel avec tous les points (limite de 15) ; optimisation
  de l'ordre (écartée par le mainteneur : ordre du rang).

## R4. Débit partagé et erreurs

- **Décision** : limiteur de débit dans l'API (4 requêtes par seconde, marge sous la limite
  de 5) et nouvelle tentative avec attente croissante sur `429` ou `5xx` ; au-delà, message
  clair et aucun GPX partiel (cas limite de la spec). Quota de 20 parcours par compte et par
  jour (FR-013).

## R5. GPX

- **Décision** : GPX 1.1 produit avec la bibliothèque standard (aucune dépendance) : une
  trace (`trk`) pour la boucle, un point de passage (`wpt`) par point visité dans l'ordre,
  nommé « ordre · niveau · désignation », avec rang, identifiant et lien vers la fiche en
  description ; métadonnées : commune, date du rapport, sources et licences, sans donnée de
  compte (FR-008, FR-012). Validé contre le schéma GPX 1.1 dans les tests.

## R6. Carte et feuille de route

- **Décision** : page de résultat servie par l'API avec la carte SVG du rapport (002)
  complétée de la boucle et des numéros de visite, et une feuille de route imprimable (feuille
  de style d'impression, une page A4 pour une vingtaine de points). Le rapport stocké n'est
  pas modifié ; FR-010 est satisfait sur cette page, qui reprend la carte du rapport.

## R7. Données de la demande

- **Décision** : le parcours calculé (paramètres, ordre, tracé, résumé) est gardé dans une
  table éphémère, expirée à 24 h et purgée au début de chaque lot (comme les liens de
  connexion de 002), le temps de consulter et télécharger ; l'adresse saisie n'est jamais
  écrite en clair dans les journaux (FR-012, SC-006).

## R8. Points déjà relevés (US4, après 003)

- **Décision** : option active seulement si les tables de 003 existent ; exclusion des
  points dont le dernier relevé visible date de moins de N jours (choisi par l'agent).
