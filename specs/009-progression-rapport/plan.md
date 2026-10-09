# Plan de mise en œuvre : progression en pourcentage de la génération d'un rapport

**Branche** : `009-progression-rapport` | **Date** : 2026-10-09 | **Spec** : [spec.md](spec.md)

**Entrée** : spécification `specs/009-progression-rapport/spec.md` (issue #55).

## Résumé

Le calcul d'une commune signale son avancement par une fonction facultative
`(phase, fait, total)` : sources globales, points un par un, analyses par l'IA point P1 par
point P1, mise en forme. Le job convertit ces appels en pourcentage borné par phase
(0-5, 5-20, 20-97, 97-99 ; jamais 100), l'écrit dans la demande au plus toutes les 5 s et à
chaque changement de phase, sans jamais le faire reculer, et estime l'heure de fin pendant
les analyses par l'IA. La page de suivi, rechargée toutes les 15 s sans script, affiche le
pourcentage, une barre native, la phase et la durée restante ; « Mes demandes » affiche
« en cours (N %) ». Décisions détaillées : [research.md](research.md).

## Contexte technique

**Langage/version** : Python 3.14 (uv, `.python-version`).

**Dépendances principales** : FastAPI et Jinja2 (pages), psycopg 3 et psycopg_pool (base),
existantes ; aucune dépendance nouvelle.

**Stockage** : PostgreSQL (Scaleway Serverless SQL) : deux colonnes facultatives sur
`demande` (migration `006_avancement.sql`) ; stockage objet inchangé.

**Tests** : pytest ; base PostgreSQL locale (`docker compose`) ; fixtures figées de
Courbevoie pour le calcul (aucun réseau).

**Plateforme cible** : conteneur sans serveur (API) et job Scaleway (lot), inchangés.

**Type de projet** : service web + job de lot (un seul paquet `src/bitumap`).

**Objectifs de performance** : la génération n'est pas ralentie de plus de 2 % (SC-004) :
environ 100 écritures d'une ligne pour 8 min de génération.

**Contraintes** : aucun script dans les pages (CSP inchangée) ; aucun coût au repos ;
pourcentage croissant, jamais 100 avant le rapport ; une erreur d'écriture de
l'avancement n'interrompt jamais la génération.

**Échelle** : une demande en cours par lot ; quelques usagers simultanés sur une même page
de suivi.

## Vérification de la constitution

*Porte : avant la phase 0, revue après la phase 1.*

| Principe | Vérification | Résultat |
|---|---|---|
| I. Sécurité d'abord | Aucun point d'accès ni script nouveau ; pages réservées aux demandeurs (contrôle existant de `suivi_de`) ; seuls pourcentage, phase et heure estimée exposés (FR-009). | Conforme |
| II. Zéro coût au repos | Écritures faites par le job pendant qu'il travaille ; rechargement de page seulement pendant une génération (base active) ; rien ne tourne au repos. | Conforme |
| III. Sources | Aucune source nouvelle. | Sans objet |
| IV. Méthode reproductible | Le calcul et les scores sont inchangés ; la fonction d'avancement n'a aucun effet sur le résultat (test : même résultat avec et sans). | Conforme |
| V. IA encadrée | Appels, plafond et cache de l'IA inchangés ; un point compte comme traité quel que soit le résultat. | Conforme |
| VI. Terrain | Sans effet sur les rapports stockés ni les relevés. | Sans objet |
| VII. Simplicité et tests | Paramètre facultatif plutôt que couplage du calcul à la base ; pas de fil d'exécution ni de point d'accès JSON ; tests unitaires, base, pages, et calcul réel figé. | Conforme |
| VIII. Retour d'expérience | Constat de l'étape « démarrage » trompeuse (R1) traité par la spec ; pas d'incident. | Conforme |
| IX. Agents | Branche dédiée, PR, essai des interfaces par le mainteneur avant fusion (LL-031). | Conforme |

Revue après la phase 1 : inchangée, aucune entorse à justifier.

## Structure du projet

### Documentation (cette fonctionnalité)

```text
specs/009-progression-rapport/
├── plan.md              # ce fichier
├── research.md          # phase 0 : R1 à R7
├── data-model.md        # phase 1 : colonnes, transitions, phases
├── quickstart.md        # phase 1 : validation
├── contracts/
│   └── progression.md   # fonction d'avancement, écriture, affichage
├── checklists/
│   └── requirements.md
└── tasks.md             # phase 2 (/speckit-tasks)
```

### Code source (racine du dépôt)

```text
src/bitumap/
├── db/migrations/006_avancement.sql   # nouveau : avancement, fin_estimee, étapes
├── calcul.py                          # paramètre avancement (sources, points, ia)
├── ia/age_enrobe.py                   # AnalyseurAge : avancement après chaque point P1
├── lot/
│   ├── progression.py                 # nouveau : pourcentage, cadence, fin estimée
│   ├── prise_en_charge.py             # avancer() ; remise à NULL aux transitions
│   └── commune.py                     # branche la progression ; plus d'étapes acquisition/calcul
└── api/
    ├── demandes.py                    # durée restante pour le gabarit (heure de Paris)
    └── gabarits/
        ├── suivi.html                 # pourcentage, <progress>, phase, durée ; refresh 15 s
        └── demandes.html              # « en cours (N %) »

tests/
├── unit/test_progression.py           # nouveau : conversion, cadence, fin estimée
├── lot/test_lot.py                    # écriture en base, transitions, garde en_cours
├── api/test_suivi_progression.py      # nouveau : pages de suivi et liste
└── non_regression/                    # ordre des appels sur Courbevoie, résultat inchangé
```

**Décision de structure** : paquet unique existant ; la logique de progression est isolée
dans `lot/progression.py` (pure, testable sans base), l'écriture dans
`lot/prise_en_charge.py` comme les autres transitions de la demande.

## Suivi de la complexité

Aucune entorse à la constitution : section sans objet.
