# Backlog

Idées retenues, pas encore planifiées. Source : branche `claude/ecstatic-sagan-9wq8qv` (projet parallèle QuestForge) et sessions précédentes.

## À faire ensuite
- **Arène de révision (Leitner)** : écran qui présente les questions dues (le backend programme déjà les révisions, aucun écran ne les montre).
- **Export Anki** des cartes de révision.

## Noté pour plus tard
- **Simulateur d'entretien** (freelance DevOps/SecOps) : pertinent pour l'objectif de départ. À lire `src/components/InterviewSimulatorModal.tsx` de la branche parallèle avant de décider du format (questions fixes ou générées par Ollama, notation).

## Écarté pour l'instant
- Simulateur de SLO, post-mortem, War Room, duels, ligues : fonctions simulées dans le navigateur, sans valeur pédagogique prouvée.

## Déjà parqué (app-core)
- Pas de fiche de révision imprimable ; le rang n'est pas lié au boss ; pas de mini-cours pour un sujet imposé ; le QCM donne 40 XP même si tout est faux  ; « Veille du jour » (plan à part) ; modules DevOps ; vidéo.
- Déploiement : images Docker en tags flottants (digests non figés : impossible de distinguer l'index multi-arch d'un manifeste unique avec podman, à faire avec `docker buildx imagetools inspect`) ; `docker compose` et Caddy jamais lancés (l'image, elle, a été construite et lancée avec podman : 401/200/403 et healthcheck OK).
