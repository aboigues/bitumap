# Contrat HTTP (phase 1) : navigation et recherche de communes

Complète `specs/002-on-demand-report/contracts/http-api.md`. Toutes les routes exigent une
session (sinon : page HTML ⇒ `303` vers l'accueil avec `motif=session`, JSON ⇒ `401`,
comportement de LL-030). En-têtes de sécurité et CSP inchangés.

## Routes nouvelles ou modifiées

| Route | Entrée | Réponse | Erreurs |
|---|---|---|---|
| `GET /communes?q=` **(modifiée)** | `q` : 1 à 100 caractères (moins de 3 ⇒ nom exact seulement, FR-016) ; 5 chiffres ⇒ code postal (002, inchangé) | page de choix : 10 communes au plus, cases à cocher radio, anti-robot, « Demander le rapport » | `q` vide ou trop court sans nom exact ⇒ page avec « Saisissez au moins 3 lettres » ; aucune commune ⇒ message « Le service couvre l'Île-de-France » (FR-007) ; API Géo indisponible pour un code postal ⇒ message invitant à chercher par le nom (FR-003) |
| `GET /communes?code_postal=` | conservée (anciens liens, formulaires en cache) | identique à 002 | identiques à 002 |
| `GET /communes?insee=` **(nouvelle)** | code INSEE de la liste intégrée | page de choix avec cette seule commune, cochée | `404 code_inexistant` hors liste |
| `GET /communes/recherche?q=` **(nouvelle)** | `q` : 1 à 100 caractères, nom seulement ; moins de 3 ⇒ nom exact seulement | JSON `[{insee, nom, departement}]`, 10 au plus ; `[]` si aucune ; `Cache-Control: private, max-age=3600` | `q` hors bornes ⇒ `[]` (aucune erreur pendant la frappe) |
| `GET /terrain` **(nouvelle)** | `q` facultatif | page « Relevés terrain » : recherche, communes avec rapport disponible ⇒ `/terrain/{insee}` ; trouvée sans rapport ⇒ « Demander le rapport » (`/communes?insee=`) | — |
| `GET /parcours` **(nouvelle)** | `q` facultatif | même page, destination `/parcours/{insee}` | — |
| `GET /rapports/{insee}/{empreinte}` **(modifiée)** | — | rapport stocké + menu et fil insérés après `<body>` (R6) ; CSP calculée comme avant | inchangées |

`POST /demandes` (002) est inchangée : la page de choix lui envoie toujours `insee`.

## Script `/statique/communes.js`

Servi par l'API (`script-src 'self'`). Sur un champ `input[data-recherche-communes]` :
temporisation 150 ms, annulation de la requête précédente, liste de propositions sous le
champ (`role="listbox"`, options navigables au clavier, `aria-activedescendant`), choix ⇒
navigation vers l'adresse de destination fournie par `data-destination` (`/communes?insee=`,
`/terrain/`, `/parcours/`). Sans script, le formulaire `GET` fonctionne seul (FR-006).
