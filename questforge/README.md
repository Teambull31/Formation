# QuestForge — Appli de Formation Gamifiée (Socle V1)

Application web locale de formation technique gamifiée pour suivre une quête quotidienne (leçon écrite avec synthèse audio vocale, validation des acquis par QCM, travaux pratiques vérifiés par script dans un terminal intégré), avec progression d'XP, rangs, équipe/gacha cosmétique, affrontements de boss, répétition espacée et rituel de préparation hebdomadaire.

---

## 🚀 Lancement Rapide

### 1. Installation des dépendances

- **Python (>= 3.11)** :
  ```bash
  uv sync
  # ou avec pip
  pip install -r backend/pyproject.toml
  ```

- **Frontend & Serveur Node (Node 22)** :
  ```bash
  npm install
  ```

### 2. Démarrage de l'application

Pour lancer l'application complète (serveur full-stack avec interface web et backend FastAPI) :

```bash
npm run dev
```

L'application est immédiatement disponible sur :
- **Navigateur local (Desktop)** : `http://localhost:3000`
- **Réseau local (Téléphone / Tablette)** : `http://<ip-de-votre-machine>:3000`

Pour lancer le backend FastAPI directement en mode autonome :
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🔒 Sécurité et Garde Localhost

- Les fonctions à privilèges système (**terminal interactif pty**, **vérification par script de TP**, **tentatives de Boss**, **importation de modules**) n'acceptent que les connexions provenant de `127.0.0.1` ou `::1` (renvoient une erreur `403 Forbidden` pour tout client distant).
- Le reste de l'API (lecture de cours, synthèse audio, quiz QCM, consultation de la quête et inventaire) est parfaitement consultable depuis un smartphone sur le réseau local.

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
