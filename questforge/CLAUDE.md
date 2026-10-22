# QuestForge : consignes pour Claude Code

Application de formation technique gamifiée : quête quotidienne (leçon, QCM, TP vérifié par script), révision
espacée, gacha, boss, préparation hebdomadaire. Front React (Vite), relais Node (`server.ts`) et backend FastAPI
(`backend/`). Le contenu pédagogique vit dans `content/` (modules et boss).

## Commandes

```bash
npm install
npx tsc --noEmit                   # types (doit rester à 0 erreur)
npm test                           # vitest : front et relais (server/)
npm run build                      # build de production du front
cd backend && uv run --with pytest --with fastapi --with httpx --with websockets --with pydantic pytest -q
npm run dev                        # démo complète sur http://localhost:3000 (voir DEPLOY.md pour le venv Python)
scripts/smoke.sh <url> [mot-de-passe]   # test de fumée d'un serveur en marche
```

Un seul test backend échoue sans `espeak-ng` : `test_audio`. C'est attendu, ne le « corrigez » pas.

## Déployer

Voir `DEPLOY.md`. En bref : `cp .env.example .env`, renseigner `QUESTFORGE_PASSWORD` (12 caractères minimum),
puis `docker compose up -d --build` (ajouter `COMPOSE_PROFILES=https` et `DOMAIN` pour un VPS public).
Mise à jour : `scripts/update.sh`. Sauvegarde : `scripts/backup.sh`.
Après tout déploiement, lancez `scripts/smoke.sh` et rapportez son résultat tel quel.

**Premier déploiement** : l'image Docker n'a jamais été construite par ceux qui l'ont écrite (pas de démon Docker
dans leur environnement). Si `docker compose up --build` échoue, diagnostiquez et corrigez le `Dockerfile`,
relancez, puis dites précisément ce qui a changé.

## Règles de sécurité (ne pas contourner)

- Le terminal et les scripts de TP exécutent des commandes sur la machine. Ne définissez jamais `HOST` sur une
  adresse non locale sans `QUESTFORGE_PASSWORD` : `server.ts` refuse, et c'est voulu.
- Le backend n'accepte les actions sensibles (terminal, `/api/tp/*/check`, `/api/boss/attempt`, `/api/weekly/import`)
  que via `backend/app/security.py` (`is_trusted`). N'ajoutez pas de route qui exécute du code sans cette garde.
- Ne publiez jamais le port 3000 sur Internet sans HTTPS, ne committez jamais `.env`, n'affichez jamais le mot de
  passe dans les journaux, les sorties de commandes ou les messages de commit.
- Le terminal et les scripts de TP reçoivent un environnement nettoyé (`clean_env`) : gardez-le ainsi.

## Architecture utile

- `src/api.ts` : client HTTP. Sans backend joignable, il bascule sur des données locales simulées (« mode démo »,
  bandeau affiché). Le mode démo ne vérifie rien : les TP y réussissent toujours et les boss sont simulés.
- `backend/app/` : `main.py` (routes), `quests.py`, `review.py` (Leitner), `boss.py`, `tp.py` (exécution des
  vérifications), `terminal.py` (pty en WebSocket), `security.py`.
- Un parcours = `content/modules/<id>/` avec `module.json`, `lessons/<id>.md`, `.qcm.json`, `.tp/tp.json` et
  `.tp/check.sh`. Les TP Terraform délèguent à `lessons/_hcl_check.py` (analyse statique, sans réseau).
- Un boss = `content/bosses/<id>/boss.json` avec des phases dont `check` est un script du même dossier.
- Variables : `QUESTFORGE_PASSWORD`, `HOST`, `PORT`, `QUESTFORGE_DATA_DIR` (base et dossier de travail),
  `QUESTFORGE_CONTENT_DIR`.

## Conventions

- Textes de l'interface et messages en français. Commits en anglais, au format `type(questforge): résumé`.
- Toute correction de bug s'accompagne d'un test qui échoue avant et passe après.
- Les fonctions annexes (War Room, Duels, Ligues, Défis…) vivent dans le navigateur : ne les présentez pas
  comme des fonctions serveur ou IA tant que ce n'est pas vrai.
