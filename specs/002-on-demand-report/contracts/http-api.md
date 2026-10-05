# Contrat : interface HTTP (conteneur API)

Pages HTML rendues par le serveur (pas d'application JavaScript lourde) ; seul script
client : le widget ALTCHA, servi par l'API elle-même. Toutes les réponses portent :
`Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'
'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action
'self'`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Permissions-Policy`. Aucun en-tête
`Server` (image lancée avec `--no-server-header`). Exceptions : le rapport (CSP propre,
ci-dessous) et les pages de terrain de 003 (géolocalisation, envoi présigné vers le bucket
`bitumap-terrain`).

Session : cookie `__Host-session` ; `POST` exige le champ `csrf` égal au jeton de session.
Erreurs : page ou JSON `{ "erreur": "<code>", "message": "<texte pour l'utilisateur>" }`,
jamais de trace technique (FR-025).

## Connexion

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /` | — | page d'accueil ; formulaire e-mail si non connecté, formulaire code postal sinon ; information RGPD | — |
| `GET /altcha/defi` | — | défi ALTCHA (JSON, valable 10 min) | `429` |
| `POST /connexion` | `email`, `altcha` | **toujours** la même page « si l'adresse est valide, un lien vient d'être envoyé » (FR-006b) | `400 antibot_invalide`, `429 trop_de_demandes` |
| `GET /connexion/{jeton}` | jeton du lien | pose la session, redirige vers `/` | `410 lien_expire_ou_utilise` |
| `POST /deconnexion` | `csrf` | supprime la session | — |
| `GET /compte` | — | adresse du compte, formulaire de suppression (session requise) | `401` |
| `POST /compte/suppression` | `csrf`, `confirmation` (« SUPPRIMER ») | supprime compte, sessions, liens, rattachements (FR-027) ; `303` vers `/` | `400 confirmation_requise`, `403 csrf_invalide`, `401` |
| `GET /confidentialite` | — | information RGPD : finalité, données, durées, droits (FR-027), liée depuis l'accueil avant toute création de compte | — |

## Demande de rapport (session requise)

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /communes?code_postal=` | code postal | liste `[{insee, nom, departement}]` (arrondissements pour Paris) | `400 format_invalide`, `400 hors_ile_de_france`, `404 code_inexistant`, `401` |
| `POST /demandes` | `insee`, `altcha`, `csrf` | `303` vers `/rapports/{insee}/{empreinte}` si en cache ; sinon `303` vers `/demandes/{id}` | `400 antibot_invalide`, `400 commune_invalide`, `429 quota_compte`, `429 quota_global`, `429 budget_ia_epuise`, `401` |
| `GET /demandes` | — | mes demandes : commune, état, date, lien | `401` |
| `GET /demandes/{id}` | — | suivi : état, position, heure estimée, étape, lien final ; rafraîchissement automatique toutes les 30 s | `404` (demande inconnue ou non rattachée au compte), `401` |

Règles `POST /demandes` : validation de l'antibot → cache (empreinte calculée à partir de la
table `source_version`, du modèle d'IA et de la version de méthode ; rapport de moins de
30 jours) → rattachement à une demande active de même empreinte → budget IA du jour (déjà
épuisé ⇒ `budget_ia_epuise`) → quota compte → quota global → création `en_file`. Le cache et
le rattachement ne consomment aucun quota (FR-005 : la consultation d'un rapport existant
n'est pas limitée) ; les quotas sont décomptés dans la transaction qui crée la demande.

Heure estimée = prochain déclenchement + ⌈position / 10⌉ × durée moyenne d'un lot récent.

## Rapports (session requise)

| Méthode, chemin | Réponse | Erreurs |
|---|---|---|
| `GET /rapports/{insee}/{empreinte}` | `rapport.html` lu dans le stockage privé et renvoyé par l'API ; `Content-Disposition: inline` ; `Cache-Control: private, no-store` ; bloc `releves` inséré à la consultation (ci-dessous) | `401`, `404` |
| `GET /rapports/{insee}/{empreinte}/points.geojson` | données des points | `401`, `404` |

Rapport servi (003) : le document stocké est figé ; à chaque consultation, l'API y insère,
juste après le bloc `donnees` et avant le script qui le lit (LL-012), un bloc
`<script type="application/json" id="releves">` : dernier relevé visible de chaque point
(contrat de 003, `specs/003-terrain-releves/contracts/http-api.md`). CSP du rapport :
`default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'sha256-…';
base-uri 'none'; form-action 'none'; frame-ancestors 'none'`, où l'empreinte est calculée
**sur les scripts en ligne du document servi** (blocs JSON exclus ; aucun script ⇒
`script-src 'none'`) et non sur le script du code en cours : un rapport en cache produit par
une version antérieure reste fonctionnel (LL-011).

## Parcours de surveillance (006, session requise)

Routes `/parcours/…` (formulaire, calcul, résultat, GPX) : voir
[le contrat de 006](../../006-parcours-surveillance/contracts/http-api.md). Mêmes en-têtes et
même CSP que les autres pages de l'API ; aucun script.

## Exploitation

| Méthode, chemin | Réponse |
|---|---|
| `GET /sante` | `200 {"etat":"ok"}` sans accès base (sonde du conteneur) |
| `GET /.well-known/security.txt` | RFC 9116 : `Contact` (signalement privé GitHub, réglage `BITUMAP_CONTACT_SECURITE`), `Expires` glissant à 180 jours, `Preferred-Languages`, `Canonical` |

## Limites

`POST /connexion` : 3/h par adresse, 10/h par origine ; `POST /demandes` : 5/jour par compte,
50/jour au total ; `GET /altcha/defi` : 60/h par origine. Valeurs dans
[configuration.md](configuration.md).
