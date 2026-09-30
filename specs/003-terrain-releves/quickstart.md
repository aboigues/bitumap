# Quickstart : valider les relevés terrain (003)

Guide de validation de bout en bout. Contrats : [contracts/http-api.md](contracts/http-api.md) ;
données : [data-model.md](data-model.md) ; décisions : [research.md](research.md).

## 1. Prérequis

- Environnement de développement de 002 (README, section Développement) : `.env` avec
  `BITUMAP_DB_PORT`, `BITUMAP_S3_PORT`, mot de passe et secrets locaux ;
  `docker compose up -d --wait db s3` ; migrations appliquées (dont `003_releves.sql`).
- Un rapport de Courbevoie produit localement (quickstart de 002, § 2).
- `BITUMAP_EMAIL_MAINTENEUR` défini dans `.env` sur une adresse de test.
- Tests automatiques : `uv run pytest tests/terrain tests/api/test_rapport_releves.py`.

## 2. Parcours principal (US1, US2)

| Étape | Action | Résultat attendu |
|---|---|---|
| Saisie | agent A connecté ; `/terrain/92026` ; point « Paix - Verdun » (A23742) ; niveau « marqué », 18 mm à la règle et cale, année 2019 « services techniques », 2 photos | relevé enregistré, confirmation ; photos visibles par A |
| Rapport | agent B ouvre le rapport de Courbevoie | fiche A23742 : section « Constaté » (marqué, 18 mm, 2019, « agent XXXX · domaine », « 2 photos, visibles par leur auteur ») ; marqueur sur la carte ; filtre « relevés, marqué ou grave » ; synthèse estimé × constaté |
| Cohérence | niveau « léger » avec 25 mm | avertissement « correspond à grave » ; corriger ou confirmer ; confirmé ⇒ `incoherence_confirmee` |
| Score inchangé | comparer score, rang et niveau de A23742 avant et après | identiques (SC-004) |
| Photos | B demande `/terrain/photos/{id}` | `404` ; A et le mainteneur : image sans métadonnée (SC-006, SC-009) |

## 3. Hors réseau (FR-004, SC-003)

- Téléphone en mode avion : saisir un relevé avec une photo ⇒ « 1 en attente d'envoi ».
- Rétablir le réseau ⇒ envoi automatique, compteur à 0 ; aucun doublon après un second
  réenvoi forcé (idempotence).
- Relevé en attente depuis plus de 3 jours (horloge simulée) ⇒ alerte visible.

## 4. Correction, retrait, suppression de compte (US3, US5)

- A corrige son relevé (« grave ») ⇒ version 2 affichée, version 1 dans l'historique.
- B tente de corriger le relevé de A ⇒ `403 pas_auteur`.
- Le mainteneur retire une photo (RGPD) ⇒ plus visible nulle part ; plus aucune version de
  l'objet dans le bucket ; trace du retrait conservée.
- A supprime son compte ⇒ relevés visibles « auteur supprimé » ; photos visibles par le
  seul mainteneur.

## 5. Export (US4)

- `releves.csv` s'ouvre dans un tableur (accents corrects), `releves.geojson` dans un
  logiciel de cartographie (SC-007).
- `echantillon_refection.json` contient A23742 avec `refection_annee: 2019` ; il est accepté
  par `uv run python -m bitumap.ia.evaluer --echantillon … --modeles …` (sans appel réel :
  vérifier seulement la lecture).

## 6. Sécurité et limites

- Photo au contenu non image (fichier texte renommé `.jpg`) ⇒ `400 image_invalide`, objet de
  quarantaine supprimé.
- 6ᵉ photo sur un relevé ⇒ `409 trop_de_photos` ; 201ᵉ relevé du jour ⇒ `429`.
- Plafond de stockage atteint (valeur forcée basse) ⇒ `507 stockage_plein` et une alerte au
  mainteneur par jour.
- Rapport produit avec une ancienne version du script (fichier de test) ⇒ toujours
  interactif (CSP calculée sur le document servi, R2).
