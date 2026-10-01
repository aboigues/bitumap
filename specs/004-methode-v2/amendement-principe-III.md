# Amendement proposé : principe III, liste des sources (004 T043)

**Statut** : texte préparé pour le mainteneur. La modification de
`.specify/memory/constitution.md` reste une PR humaine (CODEOWNERS, principe IX) ; aucun
agent ne la modifie.

**Nature** : amendement **MINEUR** (élargissement d'un principe, règle de gouvernance :
« MINEUR pour un ajout ou un élargissement ») ; version **1.4.0 → 1.5.0**.

**Préalable à** : la mise en service de la méthode 2.0 (`BITUMAP_METHODE=2.0`). Tant que la
1.2 est seule en service, les nouvelles sources ne servent qu'en développement et en
validation.

## Texte actuel

> - Seules des sources ouvertes sont utilisées en V1 : IDFM, OpenStreetMap, IGN (RGE ALTI,
>   BD TOPO, orthophotos), Institut Paris Region, Panoramax.

## Texte proposé

> - Seules des sources ouvertes sont utilisées : IDFM, OpenStreetMap, IGN (RGE ALTI,
>   BD TOPO, orthophotos, LiDAR HD), Institut Paris Region, Panoramax, Météo-France (données
>   climatologiques quotidiennes), comptages routiers publiés par les départements et l'État,
>   USGS Landsat Collection 2 (température de surface, lue sur la copie de Microsoft
>   Planetary Computer, **service hors UE déclaré**).

Les autres règles du principe III sont inchangées ; la dernière (« Tout appel à un service
hors de l'UE … est déclaré dans le plan et dans le rapport, avec la nature des données
transmises ») s'applique à Planetary Computer.

## Impact sur les specs et plans en cours

| Source ajoutée | Utilisée par | Licence | Données transmises | Déclaration |
|---|---|---|---|---|
| IGN LiDAR HD (MNS, MNT) | 004 US1 (ensoleillement) | Licence Ouverte Etalab 2.0 | coordonnées d'un carré de 200 m autour de chaque point | rapport : section Sources |
| Météo-France, données quotidiennes | 004 US2 (été de référence), 007 (projection) | Licence Ouverte 2.0 | aucune (fichier départemental téléchargé) | rapport : section Sources |
| Comptages routiers (Hauts-de-Seine, réseau national) | 004 US3 (poids lourds) | Licence Ouverte | emprise de la commune (Hauts-de-Seine) ; aucune (réseau national) | rapport : section Sources ; catalogue `src/bitumap/sources/comptages.toml` |
| USGS Landsat C2 L2 via Microsoft Planetary Computer | 004 US2 (température de surface) | domaine public | emprise de la commune et été demandé ; **aucune donnée personnelle** | rapport : section Sources, mention « service hors UE » ; research R3 ; CHANGELOG 2.0 |

- **004** : conforme une fois l'amendement adopté ; research R1, R3, R4, R5 décrivent chaque
  source (accès, licence, volume mesuré).
- **007** : partage les données Météo-France (FR-008 de 004) ; aucune autre source ajoutée.
- **002, 003, 006** : non concernées.

## Message de commit proposé

```text
docs(constitution): 1.5.0 — principe III, sources de la méthode 2.0

Ajoute à la liste des sources ouvertes : IGN LiDAR HD, Météo-France (données quotidiennes),
comptages routiers des départements et de l'État, USGS Landsat C2 via Microsoft Planetary
Computer (service hors UE déclaré). Préalable à la mise en service de la méthode 2.0 (004).
```
