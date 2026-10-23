# Backlog

Idées retenues, pas encore planifiées. Source : branche `claude/ecstatic-sagan-9wq8qv` (projet parallèle QuestForge) et sessions précédentes.

## À faire ensuite
- **Arène de révision (Leitner)** : écran qui présente les questions dues (le backend programme déjà les révisions, aucun écran ne les montre).
- **Défi Feynman** : expliquer un concept à un junior ; notation par Ollama (à valider, la liste de concepts du projet parallèle est figée en dur).
- **Export Anki** des cartes de révision.

## Noté pour plus tard
- **Simulateur d'entretien** (freelance DevOps/SecOps) : pertinent pour l'objectif de départ. À lire `src/components/InterviewSimulatorModal.tsx` de la branche parallèle avant de décider du format (questions fixes ou générées par Ollama, notation).

## Écarté pour l'instant
- Simulateur de SLO, post-mortem, War Room, duels, ligues : fonctions simulées dans le navigateur, sans valeur pédagogique prouvée.

## Déjà parqué (app-core)
- Pas de fiche de révision imprimable ; le rang n'est pas lié au boss ; pas de mini-cours pour un sujet imposé ; le QCM donne 40 XP même si tout est faux ; URL Ollama codée en dur dans `backend/app/llm.py` ; « Veille du jour » (plan à part) ; modules DevOps ; vidéo.
- Déploiement : pas de limite d'essais sur le mot de passe ; images Docker en tags flottants ; l'image Docker et `docker compose` n'ont jamais été testés pour de vrai.
