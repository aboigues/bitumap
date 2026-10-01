# Contrat : interface HTTP des relevés terrain (003)

Complète [le contrat de 002](../../002-on-demand-report/contracts/http-api.md) : mêmes
en-têtes de sécurité, même session (`__Host-session`), même jeton `csrf` sur chaque requête
qui modifie, mêmes erreurs `{ "erreur": "<code>", "message": "<texte>" }` sans détail
technique. **Toutes les routes exigent une session** (`401` sinon).

## Pages de terrain (téléphone)

| Méthode, chemin | Réponse |
|---|---|
| `GET /terrain/{insee}` | liste des points du rapport en vigueur (désignation, niveau, dernier constat), recherche et filtre ; compteur « en attente d'envoi » |
| `GET /terrain/{insee}/{point_id}` | fiche de saisie d'un relevé, historique du point |
| `GET /terrain/manifeste.webmanifest` | manifeste d'application (ajout à l'écran d'accueil, R3) |

En-têtes propres à ces pages : `Permissions-Policy: geolocation=(self)` ;
`connect-src 'self' https://bitumap-terrain.s3.fr-par.scw.cloud` (envoi direct des photos,
R4) ; `img-src 'self' blob: data:` (aperçu des photos avant envoi).

## Relevés

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `PUT /terrain/releves/{id}` | JSON : `commune_insee`, `point_id`, `cree_le`, `niveau`, champs facultatifs (data-model), `lon`/`lat` facultatifs, `confirme_malgre_incoherence` (booléen), `csrf` | `201` créé, `200` si le même relevé existe déjà (idempotent) ; si la profondeur contredit les repères du niveau et que `confirme_malgre_incoherence` est faux : `200` **sans enregistrement**, `{"avertissement": "mesure_incoherente", "niveau_suggere": "grave"}` (l'agent corrige ou confirme) | `400 niveau_requis`, `400 saisie_invalide`, `404 point_inconnu`, `409 identifiant_pris` (id d'un autre compte), `429 quota_releves` |
| `POST /terrain/releves/{id}/versions` | champs modifiables, `version` attendue (facultative : rend le réenvoi idempotent), `confirme_malgre_incoherence`, `csrf` | `201` nouvelle version ; `200` si la même version au même contenu existe déjà ; même avertissement de cohérence que la saisie | `400`, `403 pas_auteur`, `404` (inconnu ou retiré), `409 version_prise` (version déjà prise ou non consécutive) |
| `POST /terrain/releves/{id}/retrait` | `csrf`, `motif` (facultatif, 200 caractères ; défaut « erreur », « RGPD » pour le mainteneur), `rgpd` (booléen, pris en compte pour le mainteneur seul) | `200` ; relevé masqué, trace conservée (qui, quand, motif) ; rejoué : sans effet | `403 pas_auteur` (sauf mainteneur), `404` |
| `GET /terrain/releves/{id}` | — | relevé, versions, nombre de photos ; photos seulement pour l'auteur ou le mainteneur | `404` |

## Photos (R4, R5)

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `POST /terrain/releves/{id}/photos/{photo_id}/formulaire` | `csrf`, `octets` annoncés | formulaire d'envoi signé (URL, champs), valable 5 min, taille ≤ 10 Mo, `image/jpeg` ou `image/png` | `403 pas_auteur`, `409 photo_retiree` (photo retirée : aucun nouvel envoi), `409 trop_de_photos` (> 5), `413 photo_trop_lourde`, `429 quota_photos`, `507 stockage_plein` |
| `POST /terrain/releves/{id}/photos/{photo_id}/confirmation` | `csrf`, `lon`/`lat`/`prise_le` facultatifs | `201` photo `visible` après contrôle et réencodage ; idempotent | `400 image_invalide` (contenu non image), `404 envoi_absent`, `409 photo_retiree` (retirée, y compris pendant l'envoi : rien n'est conservé) |
| `GET /terrain/photos/{photo_id}` | — | image JPEG sans métadonnée ; `Cache-Control: private, no-store` | `404` **aussi** quand l'utilisateur n'est ni l'auteur ni le mainteneur (aucune fuite d'existence) |
| `POST /terrain/photos/{photo_id}/retrait` | `csrf`, `motif`, `rgpd` (booléen, pris en compte pour le mainteneur seul ; sinon retrait simple) | `200` ; auteur : photo masquée, fichier conservé ; mainteneur avec `rgpd: true` : ligne conservée comme trace (`retiree_mainteneur`), aussi pour une photo déjà retirée par son auteur ; **toutes les versions** du fichier supprimées du bucket | `404` pour un autre compte (aucune fuite d'existence) |

## Export (FR-013, FR-014)

| Méthode, chemin | Réponse |
|---|---|
| `GET /terrain/{insee}/releves.csv` | UTF-8 avec BOM, `;` ; texte commençant par `=`, `+`, `-`, `@` préfixé d'une apostrophe (injection de formules) ; un relevé visible par ligne (dernière version) : relevé, point, désignation, lon, lat, niveau estimé du rapport en vigueur, niveau constaté, profondeur, instrument, année et source de réfection, observation, date, version, auteur (pseudonyme), nombre de photos, liens des photos **seulement pour les relevés de l'utilisateur** |
| `GET /terrain/{insee}/releves.geojson` | mêmes champs en `properties`, WGS 84 |
| `GET /terrain/{insee}/echantillon_refection.json` | `{"points": [{id, nom, lon, lat, refection_annee, source, groupe}]}` (relevé le plus récent de chaque point du rapport en vigueur) pour les points à année « constatée » ou « services techniques » (format de `bitumap.ia.evaluer`, 002 T072) |

## Mainteneur

| Méthode, chemin | Réponse |
|---|---|
| `GET /terrain/moderation` | recherche d'un relevé ou d'une photo par identifiant, commune ou point ; retrait RGPD (SC-008) ; accès réservé au compte `BITUMAP_EMAIL_MAINTENEUR`, `404` sinon |

## Rapport (modification de 002)

`GET /rapports/{insee}/{empreinte}` : le document servi reçoit, juste après le bloc de données
`donnees` et donc avant le script qui le lit (LL-012), un bloc
`<script type="application/json" id="releves">` avec, pour chaque point de la commune, le
dernier relevé visible (niveau, profondeur, instrument, année de réfection, observation,
date, pseudonyme d'auteur, nombre de photos, marqueur « position éloignée ») et le nombre de
relevés. La CSP autorise l'empreinte du script en ligne **du document servi** (R2). Les
photos n'y figurent jamais.

**Rapport 2.0 (004 R9)** : juste après `releves`, un second bloc
`<script type="application/json" id="classement-terrain">`, calculé à chaque consultation
depuis `points.geojson` (facteurs, membre `ete_reference`) et les relevés visibles de la
commune : `points` (points à réfection confirmée : `annee_refection`, `source_refection`,
`effet`, `annule`, `motif`, `rang`, `groupe` corrigés), `nb_points_corriges` (effet < 1,0),
`classement` (tous les points : `id`, `rang`, `groupe` corrigés). Absent d'un rapport 1.x ou
sans `ete_reference`. Rien n'est écrit dans le stockage ; aucune donnée personnelle ; bloc
JSON exclu du calcul de la CSP (LL-011).

## Limites

200 relevés et 1 000 photos par compte et par jour ; 5 photos par relevé ; 10 Mo par photo ;
plafond global de stockage des photos (`BITUMAP_PHOTOS_MAX_GO`).
