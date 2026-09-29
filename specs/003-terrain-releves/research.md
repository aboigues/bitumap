# Recherche : Relevés terrain (003)

Décisions de conception ; chaque point résout une inconnue du contexte technique du plan.

## R1. Stockage des relevés : base existante, photos en stockage objet

- **Décision** : les relevés, leurs versions, les photos (métadonnées) et les retraits sont
  des **tables de la base PostgreSQL serverless de 002** ; les fichiers photo sont dans un
  bucket privé et versionné `bitumap-terrain` (Object Storage, `fr-par`).
- **Raison** : les besoins sont transactionnels et relationnels (historique par point,
  filtres par commune, quotas, droits d'auteur, anonymisation à la suppression d'un compte,
  idempotence des envois hors réseau) ; la base existe déjà et revient à zéro au repos
  (principe II). Le bucket versionné garantit qu'aucune photo n'est écrasée.
- **Alternatives écartées** : fichiers JSON par relevé dans le stockage objet (README,
  avant 002) : ni transactions, ni requêtes par commune, ni contraintes d'unicité ; une base
  dédiée : coût et complexité sans besoin (principe VII).

## R2. Afficher le constaté dans un rapport autonome, sans le régénérer

- **Décision** : à chaque consultation, l'API insère les relevés courants de la commune dans
  le `rapport.html` servi, sous forme d'un bloc `<script type="application/json"
  id="releves">` (données, non exécutées) ; le script fixe du rapport le lit pour remplir la
  section « Constaté », les marqueurs, les filtres et la synthèse.
- **Raison** : aucune requête réseau depuis le rapport (la CSP `default-src 'none'` reste
  intacte) ; le constaté est à jour à chaque ouverture (SC-002) ; une copie enregistrée
  reste lisible hors ligne ; le rapport stocké n'est jamais modifié (score inchangé, SC-004).
- **Point de vigilance trouvé ici** : la CSP de 002 autorise l'empreinte du script **de la
  version en cours** ; un rapport produit avant une modification de ce script (encore en
  cache, 30 jours) aurait son script bloqué. **Décision** : l'empreinte autorisée est
  calculée à la volée à partir du script en ligne du document servi (qui vient du bucket
  privé, écrit par le job) ; test de non-régression avec un rapport « ancien ».
- **Alternatives écartées** : ouvrir `connect-src` au rapport et charger les relevés par
  requête (plus de surface, pas de lecture hors ligne) ; régénérer le rapport à chaque
  relevé (coût, et contraire à FR-007).

## R3. Saisie sur téléphone, hors réseau

- **Décision** : pages de saisie servies par l'API (`/terrain/…`), avec un script
  auto-hébergé (`script-src 'self'`). Chaque relevé reçoit **son identifiant côté
  téléphone** (UUID) ; il est gardé dans le stockage local du navigateur (IndexedDB, photos
  comprises) jusqu'à confirmation du serveur ; l'envoi est **idempotent** (réenvoi sans
  doublon). Renvoi automatique au retour du réseau (événement `online`) et à chaque
  ouverture ; compteur « en attente d'envoi » toujours visible.
- **Contrainte Safari** : le stockage d'un site est effacé après 7 jours sans interaction,
  sauf pour une application ajoutée à l'écran d'accueil ([WebKit, Updates to Storage
  Policy](https://webkit.org/blog/14403/updates-to-storage-policy/)). Mesures : demande de
  stockage persistant (`navigator.storage.persist()`), manifeste d'application pour l'ajout
  à l'écran d'accueil, alerte si un relevé attend depuis plus de 3 jours (SC-003 : jamais de
  perte sans avertissement).
- **Alternatives écartées** : synchronisation en arrière-plan par service worker (non
  disponible sur Safari iOS) ; application native (hors principe VII, installation).

## R4. Photos : réduction sur le téléphone, envoi direct au stockage, contrôle serveur

- **Constat** : la documentation des [limites des Serverless
  Containers](https://www.scaleway.com/en/docs/serverless-containers/reference-content/containers-limitations/)
  ne donne pas de taille maximale de requête ; une [demande
  d'évolution](https://feature-request.scaleway.com/posts/1039/increase-body-size-limit-on-containers)
  évoque environ 1 Mo. On ne dépend donc pas du passage des photos par le conteneur.
- **Décision** :
  1. sur le téléphone, la photo est redimensionnée (2 048 px au plus, JPEG) : fichier de
     quelques centaines de Ko, métadonnées d'origine perdues au passage ; la position de
     prise de vue est lue avant (ou prise sur le téléphone) et envoyée à part ;
  2. l'API délivre un **formulaire d'envoi signé** (POST présigné, 5 min) vers un préfixe de
     quarantaine du bucket, avec **taille bornée par la politique** (10 Mo, FR-003) et type
     imposé ;
  3. à la confirmation, l'API relit l'objet, **vérifie le contenu réel** (décodage de
     l'image, FR-019), le **réencode sans aucune métadonnée** (SC-006), l'écrit sous sa clé
     définitive et supprime la quarantaine ; tout échec supprime l'objet.
- **HEIC (iPhone)** : le champ n'accepte que `image/jpeg,image/png` : Safari convertit alors
  la photo en JPEG ([Coping with HEIC in the
  browser](https://shkspr.mobi/blog/2020/12/coping-with-heic-in-the-browser/)) ; le
  redimensionnement sur le téléphone réencode de toute façon.
- **Alternatives écartées** : envoi via l'API (limite de corps inconnue) ; conservation des
  EXIF (identifiants d'appareil, heure exacte, parfois nom du propriétaire).

## R5. Accès aux photos : auteur et mainteneur seulement

- **Décision** : une photo n'est servie que par l'API (`/terrain/photos/{id}`), après
  vérification de la session : auteur du relevé, ou compte mainteneur ; réponse
  `Cache-Control: private, no-store`. Aucun lien public, aucune URL présignée de lecture
  (FR-015, FR-020, SC-009). Le rapport et l'export des autres lecteurs ne contiennent que le
  nombre de photos.
- **Mainteneur** : le compte dont l'adresse est `BITUMAP_EMAIL_MAINTENEUR` (déjà utilisée
  pour les alertes, jamais versionnée) ; pas de nouveau système de rôles.
- **Alternatives écartées** : URL présignées de lecture (partageables une fois copiées).

## R6. Affichage de l'auteur sans exposer son adresse

- **Constat** : FR-010 affiche l'auteur à tous les comptes connectés ; afficher l'adresse
  e-mail complète diffuserait une donnée personnelle à tous les utilisateurs.
- **Décision** : l'auteur est affiché sous forme d'un **pseudonyme stable** et du **domaine**
  de son adresse (« agent 7F3A · ville-courbevoie.fr ») ; l'adresse complète n'est visible
  que par le mainteneur. Le pseudonyme est dérivé du compte par empreinte à clé secrète.
  À la suppression du compte : « auteur supprimé ».
- **Validé par le mainteneur** le 2026-09-29 (clarification de la spec, FR-010).

## R7. Points absents d'un nouveau rapport

- **Décision** : un relevé est rattaché à `(commune, identifiant stable du point)`, jamais
  à l'empreinte d'un rapport ; il copie au moment de la saisie le nom, la désignation et le
  niveau estimé du point. Un point absent du rapport en vigueur garde ses relevés,
  affichés dans un historique de commune « point absent du rapport en vigueur ».

## R8. Limites, quotas et coût

- **Décision** : compteurs de 002 (`compteur_quota`) : 200 relevés et 1 000 photos par compte
  et par jour (FR-018) ; plafond global de stockage des photos (`BITUMAP_PHOTOS_MAX_GO`,
  20 Go au départ, de l'ordre de quelques dizaines de centimes par mois ; tarif Object
  Storage à vérifier au déploiement) au-delà duquel les
  nouvelles photos sont refusées et le mainteneur alerté (une fois par jour).
- **Raison** : principe I (« denial of wallet ») ; le stockage objet est le seul coût qui
  croît avec les relevés.

## R9. Position de saisie

- **Décision** : position du téléphone demandée à la validation (autorisation du navigateur,
  facultative) ; au-delà de 100 m du point, le relevé est enregistré et marqué « position
  éloignée ». Les pages de saisie autorisent la géolocalisation pour elles seules
  (`Permissions-Policy: geolocation=(self)`), les autres pages restent fermées.

## R10. Export

- **Décision** : `CSV` (UTF-8 avec BOM pour les tableurs) et `GeoJSON` (WGS 84), un
  enregistrement par relevé visible ; l'« échantillon de réfection » est produit au format
  d'entrée de `python -m bitumap.ia.evaluer` (002, T072) : `{"points": [{id, nom, lon, lat,
  refection_annee, source}]}`, seulement pour les points dont l'année est « constatée » ou
  donnée par les « services techniques ».
