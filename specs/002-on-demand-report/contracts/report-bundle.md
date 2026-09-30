# Contrat : contenu d'un rapport

Dossier : `bitumap-rapports/communes/{insee}/{empreinte}/`.

## `rapport.html`

Document autonome : styles, script de filtrage et carte SVG inclus ; aucune ressource
externe ; lisible hors connexion et sur téléphone (FR-020). Sections, dans l'ordre :

1. En-tête : commune, date, version de méthode, avertissement « classe des points à relever,
   ne mesure pas l'état réel » (FR-022).
2. Synthèse : nombre de points par groupe (P1a, P1b, P1c, P2, P3), par type de point, par type de route.
3. Carte SVG : contour communal, voies très fréquentées par les bus, points colorés par
   priorité et formés par type ; sélection d'un point ⇒ fiche.
4. Liste classée : filtres priorité / type de point / type de route (FR-018).
5. Fiche point : désignation « nom · direction · voie · lignes » et identifiant IDFM du quai
   (FR-030, aussi dans la liste et l'infobulle de la carte), champs de `points.geojson`, facteurs avec provenance et statut, photo de rue
   (lien, date, licence), **vue aérienne** (lien de comparaison IGN « Remonter le temps »,
   aujourd'hui contre 2016-2020 : une réfection ou un réaménagement récent s'y voit ; couches
   désignées par leur numéro, 10 et 11, vérifié dans un navigateur), âge de l'enrobé « à
   confirmer » avec modèle et date.
6. Méthode : version, facteurs et effets, règles de priorité, **limites connues**
   (ensoleillement et îlots de chaleur à approfondir en 004).
7. Sources : nom, licence, lien, date d'extraction (principe III).

Constaté (003) : le rapport stocké ne contient aucun relevé. S'il trouve le bloc `releves`
inséré par l'API à la consultation, le script ajoute une synthèse « Constaté », un filtre
« relevé / non relevé », le dernier relevé dans la fiche point et un lien
`/terrain/{insee}/{point_id}` (historique et nouveau relevé) ; sans ce bloc (fichier ouvert
hors du service, rapport sans relevé), la synthèse « Constaté » reste masquée et aucune fiche
n'affiche de relevé. Aucune photo ni adresse e-mail : seulement
le pseudonyme de l'auteur.

## `points.geojson`

`FeatureCollection` en WGS 84 ; une `Feature` par point ; `properties` :

```json
{
  "id": "A26860",
  "type": "arret",
  "nom": "Place Mermoz",
  "direction": "Porte de Champerret",
  "designation": "Place Mermoz · vers Porte de Champerret · Boulevard Georges Clemenceau · 167, 275, N52",
  "identifiant": "quai IDFM 26860",
  "voie": "Boulevard Georges Clemenceau",
  "route": {"classement": "départementale", "gestionnaire": "Hauts-de-Seine",
            "numero": "D9B", "statut": "concordant"},
  "bus_jour": 181, "pointe_h": 14, "lignes": ["167", "275", "N52"],
  "facteurs": [
    {"nom": "pente", "valeur": 0.2, "unite": "%", "effet": 1.0,
     "provenance": "mesure", "statut": "evalue", "explication": "Pente 0,2 %"},
    {"nom": "age_enrobe", "valeur": "5–8 ans", "effet": 0.85, "provenance": "ia",
     "statut": "a_confirmer", "explication": "Réfection visible 2018–2021",
     "modele": "…", "date": "2026-10-02"}
  ],
  "panoramax": {"url": "…", "date": "2025-11-07", "licence": "CC-BY-SA-4.0", "distance_m": 9},
  "photos_aeriennes": "https://remonterletemps.ign.fr/comparer/?lon=…&lat=…&z=19&layer1=10&layer2=11&mode=split-h",
  "score": 100, "rang": 1, "priorite": "P1", "groupe": "P1a",
  "groupe_libelle": "Critique"
}
```

`direction` : terminus desservis depuis le quai (research R11), `null` si inconnue (affichée
« direction non déterminée ») ou pour un carrefour ; descriptive, sans effet sur le score.

## `sources.json`

`[{"nom", "licence", "url", "date_extraction", "portee": "regionale|communale"}]`

## `journal.json`

`{"lot_id", "debut", "fin", "durees_s": {"acquisition", "calcul", "rapport"},
"nb_points", "ia": {"modele", "version_prompt", "appels", "jetons_entree", "jetons_sortie",
"cout_eur", "non_evalues"}, "avertissements": [], "version_methode"}` — aucune donnée
personnelle.

## `ia/{point_id}.json`

Requête (sans image) et réponse brute du modèle, rejouées à l'identique pour reproduire le
rapport (principe IV).
