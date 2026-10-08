# Contrat d'interface (phase 1) : menu et fil d'Ariane

## Menu (`<nav aria-label="Menu principal">`)

| Rubrique | Libellé | Adresse | Visible pour |
|---|---|---|---|
| `accueil` | Accueil | `/` | tous |
| `demandes` | Mes demandes | `/demandes` | connecté |
| `terrain` | Relevés terrain | `/terrain` | connecté |
| `parcours` | Parcours | `/parcours` | connecté |
| `compte` | Mon compte | `/compte` | connecté |
| `moderation` | Modération | `/terrain/moderation` | mainteneur |
| `confidentialite` | Données personnelles | `/confidentialite` | visiteur |

- Entrée courante : `aria-current="page"` + soulignement épais (pas la couleur seule).
- Écran étroit (< 48 em) : `<details><summary>Menu</summary>` replié ; écran large : liste
  affichée, `summary` masqué. Aucun script.
- « Se déconnecter » reste dans l'en-tête des pages du service ; absent du rapport (R6).
- Le pied de page garde « Données personnelles » pour tous.

## Fil d'Ariane (`<nav aria-label="Fil d'Ariane"><ol>`)

Séparateur « › » ajouté par CSS (non lu) ; dernier élément sans lien, `aria-current="page"`.

| Page | Rubrique | Fil |
|---|---|---|
| `/` | accueil | *(aucun)* |
| `/communes?…` | accueil | Accueil › Choisir la commune |
| `/demandes` | demandes | Accueil › Mes demandes |
| `/demandes/{id}` | demandes | Accueil › Mes demandes › {commune} |
| `/rapports/{insee}/{empreinte}` | demandes | Accueil › Mes demandes › {commune} |
| `/terrain` | terrain | Accueil › Relevés terrain |
| `/terrain/{insee}` | terrain | Accueil › Relevés terrain › {commune} |
| `/terrain/{insee}/{point}` | terrain | Accueil › Relevés terrain › {commune} › Point {identifiant} |
| `/terrain/moderation` | moderation | Accueil › Modération |
| `/parcours` | parcours | Accueil › Parcours |
| `/parcours/{insee}` | parcours | Accueil › Parcours › {commune} |
| `/parcours/resultat/{id}` | parcours | Accueil › Parcours › {commune} › Résultat |
| `/compte` | compte | Accueil › Mon compte |
| `/confidentialite` | confidentialite | Accueil › Données personnelles |
| page d'erreur | *(aucune)* | Accueil › Erreur |

## Liens existants mis en cohérence (FR-014)

- Accueil connecté : les liens « Mes demandes · Mon compte » sous le formulaire sont
  retirés (doublons du menu).
- Page de choix : « Autre code postal » devient « Autre recherche ».
- Rapport : le bouton « Préparer un parcours de surveillance » est conservé (action propre
  à la commune).
