# Quickstart : valider le rapport à la demande

## 0. Prérequis humains (une fois)

1. **Nom de domaine d'envoi** des e-mails, vérifié dans Scaleway Transactional Email (SPF,
   DKIM, DMARC, MX) : seule dépendance non encore disponible (research R3).
2. Bootstrap complété (applications `bitumap-api`, `bitumap-job`, `bitumap-ci`, clés dans
   Secret Manager) : `infra/bootstrap/bootstrap.sh` (profil d'administration via `.env`).
3. Secret GitHub pour la publication des images (clé `bitumap-ci`, registre uniquement).
4. Outils locaux : Docker, `uv` à jour (≥ 0.12), OpenTofu, `scw`.

## 1. Tests locaux

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest                                  # unitaires, adaptateurs, API
uv run pytest tests/non_regression -v          # Courbevoie vs prototype
```

Attendus :
- **SC-003** : ≥ 80 % des P1 du prototype parmi les P1 du rapport Courbevoie ; chaque écart
  listé avec sa cause (source ou méthode).
- **SC-004** : deux exécutions sur les mêmes extractions figées ⇒ classement identique.
- **SC-005** (partiel) : aucun point sans `route.classement` (valeur ou `indetermine`).

## 2. Parcours complet en local

```bash
docker compose up -d db s3        # PostgreSQL + stockage objet simulé
uv run bitumap-migrer             # schéma de base
uv run uvicorn bitumap.api:app --reload
uv run python -m bitumap.lot      # déclenchement manuel d'un lot
```

Les e-mails sont écrits dans la console en local (aucun envoi).

| Étape | Action | Attendu |
|---|---|---|
| Connexion | saisir une adresse, antibot | page « lien envoyé » ; lien dans la console ; lien réutilisé ⇒ refus |
| Code postal | `92400` | Courbevoie |
| | `95000` | 4 communes au choix |
| | `69001`, `9240`, `99999` | refus explicites (hors IDF, format, inexistant) |
| | `75011` | Paris 11e Arrondissement |
| Demande | Courbevoie | suivi : `en_file`, position 1 |
| Lot | `python -m bitumap.lot` | étapes visibles ; rapport produit ; « e-mail » de fin dans la console |
| Cache | redemander Courbevoie | rapport servi immédiatement (SC-001) |
| Concurrence | deux comptes demandent la même commune avant le lot | une seule demande ; deux e-mails ; quota du second non décompté |
| Déconnexion | ouvrir l'URL du rapport | refus, invitation à se connecter (SC-010) |

## 3. Abus (SC-006)

- 6ᵉ demande du jour pour un compte ⇒ `quota_compte` ; preuve antibot rejouée ⇒ refus ;
  4ᵉ lien en 1 h pour une adresse ⇒ refus, réponse identique pour une adresse inconnue.
- Plafond IA forcé à 0,01 € ⇒ rapport produit, P1 « âge non évalué », avertissement
  (US4-2).

## 4. Lots (SC-002b, SC-008)

- File vide : `python -m bitumap.lot` se termine en < 30 s.
- 10 communes en file : comparer `lot.duree` à la somme des durées de ces communes lancées
  une par une (`--isoler`) : gain ≥ 30 %.

## 5. Évaluation du modèle vision (SC-012)

```bash
uv run python -m bitumap.ia.evaluer --echantillon tests/fixtures/ia/echantillon_30.json
```

Compare les modèles candidats (research R7) : exactitude de la période, coût, aucun
changement de priorité dû à l'IA seule. Le modèle retenu est reporté dans la configuration
et dans la version de méthode.

## 6. Déploiement (mainteneur)

```bash
git tag v0.1.0 && git push origin v0.1.0     # CI : analyse, SBOM, images → registre
cd infra/tofu && tofu init && tofu plan && tofu apply   # profil scw « bitumap »
```

Alerte de facturation : vérifier que l'alerte à 5 € par mois du projet `BITUMAP` existe
(OpenTofu ou console, tâche T092).

**SC-001** : après 30 minutes sans aucune requête (conteneur et base endormis), ouvrir un
rapport déjà en cache et mesurer le temps jusqu'à son affichage : moins de 10 s.

Puis refaire §2 sur l'URL publique avec une vraie adresse e-mail : e-mail reçu en < 1 min
(SC-011), rapport Courbevoie disponible en < 45 min (SC-002), aucune instance active une fois
le lot terminé (SC-008, vérifié dans Cockpit).
