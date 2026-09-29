# Contrat : job de lot

Point d'entrée : `python -m bitumap.lot` (image `job`). Déclenché par la planification du
job toutes les 15 minutes (`*/15 * * * *`, `Europe/Paris`) ; peut aussi être lancé à la main
par le mainteneur. Délai maximal d'exécution : 3 h.

## Déroulement

1. **Réveil et prise en charge** (transaction) :
   ```sql
   UPDATE demande SET etat = 'en_cours', lot_id = :lot, pris_en_charge_le = now()
   WHERE id IN (
     SELECT id FROM demande WHERE etat = 'en_file'
     ORDER BY cree_le LIMIT :taille_lot FOR UPDATE SKIP LOCKED)
   RETURNING id, commune_insee, empreinte;
   ```
   Aucune demande ⇒ fin immédiate, code 0 (SC-008 : < 30 s).
2. **Budget** : si le budget IA du jour restant ne couvre pas l'estimation d'une commune,
   ses demandes repassent `en_file` avec la mention « reportée » (demandeurs informés).
3. **Données régionales** (une fois par lot, FR-007b) : IDFM (arrêts, offre, lignes), OSM
   Île-de-France, îlots de chaleur ; réutilisées depuis le cache si à jour ; temps mesuré
   (`lot.duree_regionale_s`).
4. **Par commune**, en séquence, avec délai maximal de 30 min :
   `acquisition` (sources communales) → `calcul` (points, facteurs, IA P1, score) →
   `rapport` (HTML, GeoJSON, sources, journal) ; `demande.etape` mis à jour à chaque étape.
   Échec d'une commune ⇒ `en_echec` (ou nouvelle tentative au lot suivant si
   `tentatives < 2` et erreur transitoire) ; les autres communes continuent (FR-007d).
5. **Notification** : e-mail à chaque compte rattaché (succès ou échec, FR-007c).
6. **Clôture du lot** : durée, coûts, nombre de communes terminées, en échec et reportées
   (table `lot`) ; événement `lot.termine` dans le journal structuré.

## Journal et alertes (FR-023, FR-029 ; T069, T070, T091)

- Journal structuré : une ligne JSON par événement (`horodatage`, `niveau`, `source`,
  `message`, champs), filtrable dans Cockpit : `commune.terminee` (durées d'acquisition,
  de calcul, d'IA et de rapport, points, appels et coût IA, non évalués), `commune.en_echec`,
  `commune.reportee`, `lot.termine`. Aucune donnée personnelle.
- `journal.json` du rapport : mêmes durées par étape, statistiques IA, avertissements
  (dont « plafond de coût de l'IA atteint »).
- Alertes au mainteneur (`BITUMAP_EMAIL_MAINTENEUR`, jamais versionnée), dédupliquées par
  la table `alerte_envoyee` : communes en échec (à chaque lot), plafond IA du jour atteint
  (une par jour), lot interrompu par une erreur d'infrastructure (une par heure ; sans
  déduplication si la base est injoignable), coût IA du mois ≥ 5 € (une par mois).

## Sources indispensables et optionnelles

| Indispensables (échec de la commune si absentes) | Optionnelles (« non évalué » + avertissement) |
|---|---|
| IDFM arrêts et offre, OSM, BD TOPO tronçons | îlots de chaleur, orthophotos historiques, infrarouge, Panoramax, bâtiments (ensoleillement), altimétrie |

## Sorties

Fichiers de [report-bundle.md](report-bundle.md) sous
`bitumap-rapports/communes/{insee}/{empreinte}/`, écrits **en dernier** `rapport.html` :
sa présence signifie « rapport complet ».

## Codes de sortie

`0` : lot traité (même avec des communes en échec) ; `1` : erreur d'infrastructure (base
injoignable…) : les demandes prises en charge sont remises `en_file` par le lot suivant
après 3 h.
