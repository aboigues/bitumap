# Journal des changements de méthode

Constitution, principe IV : toute modification d'un facteur, d'une pondération, d'un seuil
ou d'une règle de priorité incrémente la version de méthode (`bitumap.score.methode`) et est
décrite ici. La version entre dans l'empreinte des rapports : un rapport produit avec une
autre version n'est jamais réutilisé.

## 1.1 — 2026-09-29

- **Sous-groupes du P1** : les P1 (toujours 20 % des points) sont découpés par rang final,
  après l'âge de l'enrobé, en trois tiers **P1a**, **P1b**, **P1c** ; le reste de la division
  va aux premiers tiers (31 P1 ⇒ 11, 10, 10). Affichés dans la synthèse, la liste, la fiche et
  la carte (points plus gros pour P1a), filtrables.
- **Raison** : à Courbevoie, 31 points P1 sur 154 n'aidaient pas à choisir par où commencer
  (retour du mainteneur).
- **Sans effet** sur les scores, les rangs, les priorités P1 / P2 / P3, le périmètre de l'IA
  (P1) ni la non-régression SC-003.

## 1.0 — 2026-09-28

- **Score** = produit des effets des facteurs, affiché de 0 à 100 relativement au maximum de
  la commune ; tri déterministe (score décroissant, puis identifiant).
- **Facteurs et effets** :
  - charge : ln(1 + bus/jour) ; carrefour : voie la plus chargée + moitié de la seconde ;
  - sollicitation : arrêt ×1,0, carrefour à feux ×0,8, giratoire ×0,7 ; arrêt à moins de
    40 m d'un feu ×1,2 ; 20 bus/h ou plus en pointe ×1,1 ;
  - site : pente ≥ 3 % jusqu'à ×1,32 ; béton ou pavés ×0,5 ;
  - ensoleillement de la chaussée (8 h–20 h, mi-juillet) : ×0,8 à ×1,2 ;
  - îlot de chaleur, aléa de jour 0–16 : ×0,92 à ×1,08 ;
  - âge de l'enrobé (IA, P1 seulement, « à confirmer ») : 5–12 ans ×0,85 ; plus de 12 ans
    ×1,05.
- **Priorités par rang** : P1 = 20 % premiers, P2 = 40 % suivants, P3 = le reste.
- **Écart assumé avec le prototype** : les priorités sont **figées avant** l'âge de
  l'enrobé, qui ne réordonne les points qu'à l'intérieur des P1 ; le prototype faisait
  descendre certains P1 en P2 (principe V : l'IA ne décide pas seule).
- **Limites connues** : ensoleillement estimé en un point, arbres de hauteur forfaitaire,
  sans relief ; îlots de chaleur : indicateur de jour de 2022 ; facteur chaleur peu
  discriminant (0,92–1,07 à Courbevoie). À approfondir en 004 (exposition climatique
  annuelle, minéralisation, climatiseurs, température de surface).
- **Non-régression** : 74 % des P1 du prototype retrouvés à Courbevoie (SC-003, écart
  accepté par le mainteneur le 2026-09-28).
