# Modèle de données (phase 1) : navigation et recherche de communes

Aucune table ni migration nouvelle. Une donnée de référence versionnée dans le paquet et
deux structures en mémoire.

## Commune de référence — `src/bitumap/territoire/communes_idf.json`

Fichier généré (R1), relu en PR, chargé une fois au démarrage.

```text
{
  "source": "API Géo (geo.api.gouv.fr), Licence Ouverte 2.0",
  "url": "https://geo.api.gouv.fr/communes?codeRegion=11…",
  "genere_le": "AAAA-MM-JJ",
  "communes": [ ["92026", "Courbevoie", "92"], … ]   // [insee, nom officiel, département]
}
```

| Champ | Règle |
|---|---|
| `insee` | 5 caractères, unique ; jamais `75056` ; `751xx` pour les 20 arrondissements |
| `nom` | nom officiel, tel que publié (accents, tirets) |
| `departement` | `75`, `77`, `78`, `91`, `92`, `93`, `94` ou `95` |

Contrôles (tests) : 1 285 entrées à la génération du 2026-10-08 (le test vérifie les
invariants, pas le nombre exact : au moins 1 200, 20 arrondissements, aucun `75056`, codes
uniques, départements d'Île-de-France) ; métadonnées `source`, `url`, `genere_le` présentes.

**En mémoire** (calculé au chargement, non stocké) : `forme` (R3) et `alias` (arrondissements).

## Proposition (réponse de recherche)

`{insee, nom, departement}` ; 10 au plus, triées selon R3. Identique pour la page sans
script et la réponse JSON.

## Entrée de menu — `src/bitumap/api/navigation.py`

| Champ | Exemple |
|---|---|
| `rubrique` | `accueil`, `demandes`, `terrain`, `parcours`, `compte`, `moderation`, `confidentialite` |
| `libelle` | « Mes demandes » |
| `adresse` | `/demandes` |
| `visible` | `connecte`, `mainteneur`, `visiteur`, `tous` |

Ordre fixe : Accueil, Mes demandes, Relevés terrain, Parcours, Mon compte, Modération
(mainteneur). Visiteur : Accueil, Données personnelles.

## Élément de fil d'Ariane

`(libelle, adresse | None)` ; liste ordonnée, le dernier élément n'a pas d'adresse. Chemins
par page : [contracts/interface.md](contracts/interface.md).

## Commune avec rapport disponible (R7)

Lecture seule, calculée à la demande : `{insee, nom}` des demandes `terminee` récentes dont
l'empreinte est l'empreinte courante. Aucune donnée de compte.
