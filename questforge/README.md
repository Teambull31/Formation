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
   - Défis multi-phases contre des patterns réels d'incidents (CrashLoopBackOff, panne DNS, timeout SSL).
   - Tentatives illimitées avec remédiation guidée vers les fiches techniques.

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
