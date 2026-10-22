# QuestForge — Appli de Formation Gamifiée (Socle V1)

Application web locale de formation technique gamifiée pour suivre une quête quotidienne (leçon écrite avec synthèse audio vocale, validation des acquis par QCM, travaux pratiques vérifiés par script dans un terminal intégré), avec progression d'XP, rangs, équipe/gacha cosmétique, affrontements de boss, répétition espacée et rituel de préparation hebdomadaire.

---

## 🚀 Lancement Rapide

Prérequis : Node 22 et Python 3.11 ou plus récent.

```bash
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" httpx websockets pydantic
npm install
PATH="$PWD/.venv/bin:$PATH" npm run dev
```

L'application est disponible sur http://localhost:3000. `npm run dev` lance le relais Node, le front et le backend
FastAPI ; le relais appelle `python3`, le venv doit donc être dans le `PATH`.

Déploiement sur un PC ou un VPS (Docker, HTTPS, mot de passe, mises à jour, sauvegarde) : voir **[DEPLOY.md](DEPLOY.md)**.
Consignes pour une session Claude Code : voir **[CLAUDE.md](CLAUDE.md)**.

---

## 🔒 Sécurité

Le terminal interactif, la vérification des TP, les combats de boss et l'import de module **exécutent des commandes** sur la machine.

- Sans `QUESTFORGE_PASSWORD`, le serveur n'écoute que sur `127.0.0.1`. Il refuse de démarrer si on l'ouvre au réseau sans mot de passe.
- Avec `QUESTFORGE_PASSWORD` (12 caractères minimum), tout est protégé par HTTP Basic, y compris l'API et le terminal. Utilisez HTTPS dès que le serveur est joignable depuis Internet.
- Le backend n'écoute que sur `127.0.0.1` et n'accepte ces actions que si le relais a authentifié la requête (secret interne) ou si elle vient directement de la machine.
- Le reste de l'API (cours, QCM, quête) est en lecture seule pour un client authentifié.

---

## 🎮 Fonctionnalités du Socle V1

1. **Quête Quotidienne** :
   - Format 30 min (Leçon 20 XP, QCM 40 XP, TP 80 XP).
   - Format 60 min avec quête bonus (+30 min, 150 XP).
   - Sujet imposé (urgences professionnelles) : préserve la série sans rupture.
   - Jours de repos annoncés : illimités, sans pénalité.

2. **Répétition Espacée (Boîtes de Leitner)** :
   - Intervalles : `[1, 2, 4, 7, 14]` jours.
   - En cas d'erreur au QCM, la question retombe en boîte 0 (échéance demain) avec lien direct vers la fiche de cours de remédiation.

3. **Terminal et Vérifications Réelles de TP** :
   - Exécution de commandes bash dans un terminal `xterm.js` pty.
   - Vérification par script déterministe (`check.sh`) avec timeout et troncature de sortie.
   - Système d'indices progressifs (-10 XP par indice) avec repli pré-écrit si Ollama (`qwen3:14b`) est inaccessible.

4. **Équipe & Gacha Cosmétique** :
   - Invocations de mascottes historiques (Ada Lovelace, Alan Turing, Grace Hopper...) et thèmes de terminal.
   - 100% cosmétique, aucun contenu de cours bloqué. Raretés pondérées : Commun (70%), Rare (25%), Épique (5%).

5. **Affrontements de Boss** :
   - Défis multi-phases vérifiés par script sur votre dossier de travail (boss `boss_terraform` : « Le Gardien du State »).
   - Tentatives illimitées avec remédiation guidée vers la fiche de la phase échouée ; récompense (+150 XP, 1 jeton) à la première victoire seulement.
   - Un boss se définit dans `content/bosses/<id>/boss.json` (phases avec un script `check`, `check_label` affiché à l'apprenant).

6. **Rituel du Dimanche (Préparation Hebdomadaire)** :
   - Générateur de prompt pour **Claude Code** contextualisé avec vos erreurs récentes et niveaux de compétence.
   - Importateur atomique : validation stricte du module (structure, QCM, TP) avant toute copie.

---

## 🧪 Tests Automatisés

- **Backend (Python pytest)** :
  ```bash
  uv run pytest -v backend/tests
  ```

- **Frontend (Vitest)** :
  ```bash
  npm test
  ```

- **Build de production** :
  ```bash
  npm run build
  ```

---

## 🧭 Parcours, modes et variables

- **Parcours** : chaque dossier de `content/modules/<id>/` est un parcours (`module.json` accepte `description` et `icon`). Le parcours actif se choisit dans l'écran Quête et se conserve en base. Le module `terraform` fournit 3 leçons avec TP guidés vérifiés par `lessons/_hcl_check.py` (analyse statique, sans binaire Terraform ni réseau).
- **Jetons de gacha** : 1 jeton quand toutes les étapes requises d'une leçon sont validées, +1 à la première victoire contre un boss.
- **Mode démo hors-ligne** : sans backend (par exemple un déploiement Vercel statique), l'interface bascule sur des données locales simulées et l'indique par un bandeau. La progression reste dans le navigateur, les vérifications de TP et les combats de boss sont simulés, et le bouton « Réinitialiser » efface cet état.
- **Fonctions annexes** (War Room, Ligues, Duels, Défis sur-mesure, etc.) : contenus embarqués dans le navigateur, sans IA ni serveur. La Ligue et la Guilde sont des simulations sans récompense.
- **Variables d'environnement** : `QUESTFORGE_CONTENT_DIR` pour utiliser un autre dossier de contenu que `content/`.
