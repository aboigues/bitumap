# Contrat : contenu d'un rapport

Dossier : `bitumap-rapports/communes/{insee}/{empreinte}/`.

## `rapport.html`

Document autonome : styles, script de filtrage et carte SVG inclus ; aucune ressource
externe ; lisible hors connexion et sur téléphone (FR-020). Sections, dans l'ordre :

1. En-tête : commune, date, version de méthode, avertissement « classe des points à relever,
   ne mesure pas l'état réel » (FR-022).
2. Synthèse : nombre de points par priorité, par type de point, par type de route.
3. Carte SVG : contour communal, voies très fréquentées par les bus, points colorés par
   priorité et formés par type ; sélection d'un point ⇒ fiche.
4. Liste classée : filtres priorité / type de point / type de route (FR-018).
5. Fiche point : champs de `points.geojson`, facteurs avec provenance et statut, photo de rue
   (lien, date, licence), âge de l'enrobé « à confirmer » avec modèle et date.
6. Méthode : version, facteurs et effets, règles de priorité, **limites connues**
   (ensoleillement et îlots de chaleur à approfondir en 004).
7. Sources : nom, licence, lien, date d'extraction (principe III).

## `points.geojson`

`FeatureCollection` en WGS 84 ; une `Feature` par point ; `properties` :

```json
{
  "id": "A26860",
  "type": "arret",
  "nom": "Place Mermoz",
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
  "score": 100, "rang": 1, "priorite": "P1"
}
```

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
