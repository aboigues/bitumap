# Guide de validation (phase 1) : navigation et recherche de communes

## 1. Prérequis

```bash
UV_PYTHON_PREFERENCE=only-managed uv sync
docker compose up -d            # base et S3 simulé (ports de .env, LL-006)
```

## 2. Tests automatiques

```bash
uv run pytest -q tests/unit/test_communes_idf.py tests/api/test_navigation.py \
  tests/api/test_recherche_communes.py tests/api/test_rapport_menu.py
uv run pytest -q                # suite complète, non-régression Courbevoie comprise
```

Attendus :

- liste intégrée : invariants de [data-model.md](data-model.md) ; SC-001 (nom complet
  toujours trouvé, 5 lettres ⇒ au moins 95 %, taux mesuré affiché) ;
- recherche : exemples du récit 1 (« courbe », « asnieres », « paris 17 », « 17e »,
  « st denis », « Lyon ») ; code postal inchangé ; API Géo en panne ⇒ message ;
- menu : entrées selon le compte (visiteur, agent, mainteneur), `aria-current`, aucune
  « Modération » pour un agent ; fil de chaque page de
  [contracts/interface.md](contracts/interface.md) ;
- rapport : menu inséré après `<body>`, rapport produit par une **version antérieure** du
  gabarit compris (LL-011), CSP identique, bloc `releves` toujours avant le script (LL-012),
  menu du compte qui consulte.

## 3. Essai dans un navigateur (obligatoire avant la PR : LL-007, LL-012, LL-017)

Serveur local `uv run uvicorn bitumap.api:app --reload` (quickstart de 002), compte de test connecté.

1. Accueil : taper « courbe » ⇒ Courbevoie (92) proposée ; flèches + Entrée ⇒ page de
   choix ⇒ demande créée. Refaire **script désactivé** : formulaire ⇒ page de résultats.
2. 360 px de large (émulation mobile) : bouton « Menu » replié, ouvert, toutes les entrées
   visibles, pas de défilement horizontal ; écran large : menu affiché sans bouton.
3. Chaque entrée du menu depuis chaque page ; entrée courante signalée ; fil d'Ariane
   conforme et ses liens fonctionnels.
4. Rapport : menu et fil présents, thème clair et sombre ; **filtres, carte, sélection d'un
   point, fiche, lien vers la saisie** inchangés ; aucune erreur CSP en console.
5. « Relevés terrain » : commune avec rapport ⇒ `/terrain/{insee}` ; commune sans rapport ⇒
   « Demander le rapport ».
6. Lecteur d'écran (NVDA ou Orca) : menu et fil annoncés, page courante identifiée.

## 4. Après déploiement

Avec le mainteneur (SC-004) : Courbevoie, Asnières-sur-Seine et Paris 17e trouvées et
demandées en moins de 30 s chacune, sans code postal.
