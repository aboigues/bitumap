# Contrat : progression de la génération (009)

Deux interfaces : la fonction d'avancement que le calcul appelle (interne au job), et
l'affichage des pages de suivi (visible de l'usager).

## 1. Fonction d'avancement (calcul → job)

```text
avancement(phase: str, fait: int, total: int) -> None
```

- Paramètre facultatif de `calculer_commune(..., avancement=None)` et de
  `AnalyseurAge(..., avancement=None)` ; `None` : aucun appel (tests, outils, CLI).
- Appels attendus, dans l'ordre :
  1. `("sources", 0, 1)` au début du calcul, `("sources", 1, 1)` une fois les sources
     globales lues ;
  2. `("points", i, n)` après chaque point de la boucle des sources ponctuelles
     (`n` = nombre de points) ;
  3. `("ia", k, m)` avant le premier appel (`k = 0`) puis après chaque point P1 traité,
     quel que soit le résultat (réponse, cache, non évalué, plafond atteint) ; `m` =
     nombre de points P1 ; aucun appel si `m = 0` ;
  4. `("rapport", 0, 1)` par `lot/commune.py`, avant le rendu.
- La fonction ne lève jamais d'exception vers le calcul : une erreur (base indisponible)
  est journalisée et ignorée.

## 2. Conversion en pourcentage et écriture (job)

```text
pourcentage = floor(debut + (fin - debut) × fait / total)   # total > 0
```

avec les bornes `(debut, fin)` : `sources` (0, 5), `points` (5, 20), `ia` (20, 97),
`rapport` (97, 99). Résultat borné à `[0, 99]`.

Écriture en base (`prise_en_charge.avancer`) :

- au changement de phase, et au plus toutes les 5 secondes à l'intérieur d'une phase
  (la dernière valeur d'une phase est toujours écrite au changement suivant) ;
- `UPDATE demande SET etape = %s, avancement = GREATEST(coalesce(avancement, 0), %s),
  fin_estimee = %s WHERE id = %s AND etat = 'en_cours'` ;
- `fin_estimee` (phase `ia`, `k ≥ 1`) = maintenant + (durée écoulée depuis `("ia", 0, m)`
  / `k`) × (`m − k`) + 15 s ; `NULL` dans les autres phases.

## 3. Affichage (API, sans script)

### Page de suivi `/demandes/{id}` (état `en_cours`)

- Rechargement automatique : `<meta http-equiv="refresh" content="15">` (30 s en file,
  inchangé).
- Avec `avancement` renseigné :

  ```html
  <p>Génération en cours : <strong>42 %</strong> — analyse des photos aériennes.</p>
  <progress max="100" value="42" aria-label="Avancement de la génération">42 %</progress>
  <p>Environ 4 min restantes.</p>   <!-- seulement si fin_estimee > maintenant -->
  ```

- Durée restante : `ceil((fin_estimee − maintenant) / 60)` minutes ; « moins d'une
  minute » si moins de 60 s ; ligne absente si `fin_estimee` est `NULL` ou passée.
- Sans `avancement` (`NULL`, ou colonne absente avant migration) : « Génération en
  cours : démarrage. », sans barre.
- Libellés : voir [data-model.md](../data-model.md), table des phases ; une valeur
  d'étape inconnue (ancienne ligne `acquisition`, `calcul`) s'affiche « génération en
  cours ».
- Autres états (`en_file`, `terminee`, `en_echec`, reportée) : affichage actuel inchangé.

### Liste « Mes demandes » `/demandes`

- Demande `en_cours` avec `avancement` : colonne état « en cours (42 %) » ; sinon
  inchangée. Pas de rechargement automatique.
