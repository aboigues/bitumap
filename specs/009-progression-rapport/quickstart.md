# Guide de validation : progression de la génération (009)

## 1. Tests automatiques

```bash
UV_PYTHON_PREFERENCE=only-managed uv run pytest -q tests/unit/test_progression.py \
  tests/lot tests/api/test_suivi_progression.py
```

Attendu : vert. Ils couvrent la conversion en pourcentage (bornes, croissance, jamais
100), la cadence d'écriture (5 s, changement de phase), l'absence d'écriture hors
`en_cours`, la durée restante, l'affichage des pages et la remise à zéro aux transitions.

## 2. Ordre des appels sur des données réelles figées

Calcul de Courbevoie sur les fixtures (`FournisseurFige`) avec une fonction d'avancement
qui enregistre ses appels : phases dans l'ordre `sources`, `points`, `ia`, pourcentage
calculé croissant, un appel `points` par point, un appel `ia` par point P1 (contrat §1).

## 3. Essai de bout en bout en local (mainteneur, LL-031)

```bash
scripts/essai/lancer.sh
```

1. Demander un rapport pour une commune sans rapport en cache, lancer le job en local
   (README, section Développement).
2. Ouvrir la page de suivi : le pourcentage et la barre apparaissent, la phase change,
   la page se recharge seule toutes les 15 s ; pendant les analyses par l'IA, une durée
   restante apparaît.
3. Ouvrir « Mes demandes » : « en cours (N %) ».
4. À la fin : lien « Ouvrir le rapport » ; jamais 100 % avant.
5. Téléphone (360 px) et thème sombre : barre et texte lisibles.

## 4. Mesures en production (après v0.1.3)

Sur une génération réelle d'au moins 5 minutes (commune sans rapport en cache), relever
la page de suivi toutes les 15 s (heure, pourcentage, durée restante) puis comparer au
`journal.json` du rapport :

- SC-001 : aucune période de plus de 60 s sans progression ;
- SC-002 : aucun relevé inférieur au précédent ; jamais 100 % ;
- SC-003 : écart au temps écoulé < 25 points pendant au moins 80 % de la durée ;
- SC-004 : durée totale comparable aux générations précédentes de taille voisine (± 2 %) ;
- SC-005 : seconde moitié des analyses IA, écart de la durée restante < 2 min.
