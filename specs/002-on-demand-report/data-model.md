# Modèle de données : Rapport de risque d'orniérage à la demande

Deux stockages : la base PostgreSQL serverless (état vivant, données personnelles
minimales) et le stockage objet (rapports immuables, cache des sources).

## Base de données

### compte

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | clé |
| `email` | texte | unique, minuscules, format validé |
| `cree_le` | horodatage | |
| `derniere_connexion` | horodatage | suppression automatique si > 12 mois (FR-027) |

### lien_connexion

| Champ | Type | Règles |
|---|---|---|
| `empreinte_jeton` | octets (SHA-256) | clé ; le jeton en clair n'est jamais stocké |
| `compte_id` | uuid | → compte (créé à la première validation si inexistant) |
| `email` | texte | adresse visée, pour créer le compte au premier usage |
| `emis_le`, `expire_le` | horodatage | `expire_le = emis_le + 15 min` |
| `utilise_le` | horodatage, nul | usage unique : mise à jour conditionnelle `WHERE utilise_le IS NULL` |

### session

| Champ | Type | Règles |
|---|---|---|
| `empreinte_id` | octets | clé |
| `compte_id` | uuid | → compte, suppression en cascade |
| `jeton_csrf` | texte | vérifié sur chaque `POST` |
| `cree_le`, `expire_le` | horodatage | 7 jours |

### preuve_antibot

| Champ | Type | Règles |
|---|---|---|
| `signature` | texte | clé : une preuve ne sert qu'une fois |
| `utilisee_le` | horodatage | purgée après 1 h |

### compteur_quota

| Champ | Type | Règles |
|---|---|---|
| `cle` | texte | `generation:compte:{id}:{jour}`, `generation:global:{jour}`, `lien:email:{empreinte}:{heure}`, `lien:origine:{empreinte_ip_salée}:{heure}` |
| `valeur` | entier | incrément atomique ; comparaison aux plafonds de `config` |
| `expire_le` | horodatage | purge ; identifiants d'origine ≤ 24 h (FR-026) |

### demande (file d'attente)

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | identifiant de suivi |
| `commune_insee` | texte | code commune ou arrondissement (751xx) |
| `empreinte` | texte | commune + version de méthode + versions des sources |
| `etat` | énuméré | voir transitions |
| `etape` | énuméré, nul | `acquisition`, `calcul`, `rapport` |
| `cree_le`, `pris_en_charge_le`, `termine_le` | horodatage | |
| `lot_id` | uuid, nul | → lot |
| `tentatives` | entier | ≤ 2 |
| `erreur_publique` | texte, nul | sans détail technique (FR-025) |

Contrainte : **unique (`empreinte`) tant que `etat` ∈ {en_file, en_cours}** (index partiel)
⇒ une seule demande active par empreinte (FR-009).

Position dans la file = nombre de demandes `en_file` créées avant elle + 1.

Transitions :

```text
en_file ──(pris en charge par un lot)──▶ en_cours ──▶ terminee
   ▲                                        │
   └──(lot interrompu > 3 h, tentatives < 2)┘──▶ en_echec
en_file ──(budget IA du jour épuisé)──▶ en_file (reportée au lendemain)
```

### demandeur_demande

| Champ | Type | Règles |
|---|---|---|
| `demande_id`, `compte_id` | uuid | clé composée ; plusieurs comptes rattachés à une même demande (US2-6), tous prévenus par e-mail |
| `compte_quota` | booléen | vrai uniquement pour le premier demandeur |

### lot

| Champ | Type | Règles |
|---|---|---|
| `id` | uuid | |
| `demarre_le`, `termine_le` | horodatage | durée ≤ 3 h |
| `nb_demandes` | entier | ≤ 10 |
| `duree_regionale_s` | réel | temps d'acquisition des données régionales (SC-002b) |
| `cout_ia_eur` | décimal | |

### cout_ia_jour

| Champ | Type | Règles |
|---|---|---|
| `jour` | date | clé |
| `montant_eur` | décimal | réservation **avant** chaque appel, ajustement après ; ≤ 20 € (FR-024) |

## Stockage objet

```text
bitumap-rapports/  (privé, versionné)
  communes/{insee}/{empreinte}/rapport.html
  communes/{insee}/{empreinte}/points.geojson
  communes/{insee}/{empreinte}/sources.json
  communes/{insee}/{empreinte}/journal.json
  communes/{insee}/{empreinte}/ia/{point_id}.json     # réponses du modèle, rejouables (principe IV)

bitumap-cache/  (privé, expiration 30 jours)
  regional/{source}/{date_extraction}/…               # IDFM, OSM IDF, îlots de chaleur
  communes/{insee}/{source}/{date_extraction}/…       # BD TOPO, altimétrie, ortho, Panoramax
```

Formats : [contracts/report-bundle.md](contracts/report-bundle.md).

## Entités du rapport

### Point

| Champ | Règles |
|---|---|
| `id` | stable (FR-016) : arrêt = `A{id_arret IDFM}` ; carrefour = `F{id nœud OSM}` ; giratoire = `G{id chemin OSM}` |
| `type` | `arret`, `feu`, `giratoire` |
| `nom`, `voie`, `lat`, `lon` | |
| `route` | `{classement, gestionnaire, numero, source, statut}` ; `classement` ∈ {autoroute, nationale, départementale, communale, communale_presumee, privee, indetermine} ; `statut` ∈ {concordant, a_verifier, indetermine} |
| `facteurs[]` | `{nom, valeur, unite, effet, provenance ∈ {mesure, estime, ia}, statut ∈ {evalue, non_evalue, a_confirmer}, explication}` |
| `score` | 0–100, arrondi, déterministe |
| `rang`, `priorite` | P1 = 20 % premiers, P2 = 40 % suivants, P3 = reste (FR-012) |

### Empreinte

`sha256(insee | version_methode | trié(source:date_extraction) | version_prompt_ia)` ; tronquée
à 16 caractères hexadécimaux dans les chemins.
