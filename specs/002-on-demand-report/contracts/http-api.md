# Contrat : interface HTTP (conteneur API)

Pages HTML rendues par le serveur (pas d'application JavaScript lourde) ; seul script
client : le widget ALTCHA, servi par l'API elle-même. Toutes les réponses portent :
`Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'
'unsafe-inline'; frame-ancestors 'none'`, `Strict-Transport-Security`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.

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
| `POST /compte/suppression` | `csrf`, confirmation | supprime compte, sessions, rattachements (FR-027) | — |

## Demande de rapport (session requise)

| Méthode, chemin | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /communes?code_postal=` | code postal | liste `[{insee, nom, departement}]` (arrondissements pour Paris) | `400 format_invalide`, `400 hors_ile_de_france`, `404 code_inexistant`, `401` |
| `POST /demandes` | `insee`, `altcha`, `csrf` | `303` vers `/rapports/{insee}/{empreinte}` si en cache ; sinon `303` vers `/demandes/{id}` | `400 antibot_invalide`, `400 commune_invalide`, `429 quota_compte`, `429 quota_global`, `429 budget_ia_epuise`, `401` |
| `GET /demandes` | — | mes demandes : commune, état, date, lien | `401` |
| `GET /demandes/{id}` | — | suivi : état, position, heure estimée, étape, lien final ; rafraîchissement automatique toutes les 30 s | `404` (demande inconnue ou non rattachée au compte), `401` |

Règles `POST /demandes` : validation de l'antibot → quota compte → quota global → cache
(empreinte calculée à partir des dates d'extraction connues) → rattachement à une demande
active de même empreinte (sans décompte du quota) → création `en_file`.

Heure estimée = prochain déclenchement + ⌈position / 10⌉ × durée moyenne d'un lot récent.

## Rapports (session requise)

| Méthode, chemin | Réponse | Erreurs |
|---|---|---|
| `GET /rapports/{insee}/{empreinte}` | `rapport.html` lu dans le stockage privé et renvoyé par l'API ; `Content-Disposition: inline` ; `Cache-Control: private, no-store` | `401`, `404` |
| `GET /rapports/{insee}/{empreinte}/points.geojson` | données des points | `401`, `404` |

## Exploitation

| Méthode, chemin | Réponse |
|---|---|
| `GET /sante` | `200 {"etat":"ok"}` sans accès base (sonde du conteneur) |

## Limites

`POST /connexion` : 3/h par adresse, 10/h par origine ; `POST /demandes` : 5/jour par compte,
50/jour au total ; `GET /altcha/defi` : 60/h par origine. Valeurs dans
[configuration.md](configuration.md).
