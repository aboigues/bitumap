# Politique de sécurité

La sécurité est le premier principe du projet (constitution, principe I). Merci de nous aider à
protéger bitumap et ses utilisateurs.

## Versions supportées

| Version | Correctifs de sécurité |
|---|---|
| branche `main` | ✅ |
| dernière version publiée | ✅ |
| versions antérieures | ❌ |

## Signaler une vulnérabilité

**Ne créez pas d'issue publique.** Signalez la vulnérabilité en privé :

1. onglet **Security** du dépôt → **Report a vulnerability** (avis de sécurité privé GitHub) ;
2. décrivez l'impact, les étapes de reproduction et, si possible, une piste de correction.

N'incluez aucun secret réel ni donnée personnelle dans votre signalement.

## Nos engagements

| Étape | Délai |
|---|---|
| Première réponse | 7 jours au plus |
| Correction d'une vulnérabilité critique | 7 jours visés |
| Correction d'une vulnérabilité élevée | 30 jours visés |

Nous vous tiendrons informé de l'avancement et, si vous le souhaitez, nous vous citerons dans
l'avis publié une fois le correctif disponible.

## Ce que nous publions

Après correction, un avis de sécurité GitHub décrit le problème et la version corrigée. Le
retour d'expérience interne (`LESSON-LEARNED.md`) ne contient jamais de détail exploitable
(constitution, principe VIII).

## Dispositifs en place

- Analyse du code, des dépendances, des secrets, des images et de l'infrastructure sur chaque
  PR, bloquante à partir de la gravité élevée ;
- mises à jour de sécurité automatiques des dépendances, fusionnées par un humain ;
- SBOM CycloneDX attaché à chaque version publiée.
