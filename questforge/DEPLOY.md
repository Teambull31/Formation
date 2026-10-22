# Déployer QuestForge (PC perso ou VPS)

QuestForge exécute des commandes : le terminal des TP et les scripts de vérification tournent sur la machine
qui héberge le serveur. C'est pourquoi **le serveur refuse de s'ouvrir au réseau sans mot de passe**
(`QUESTFORGE_PASSWORD`, 12 caractères minimum) et pourquoi il faut du **HTTPS** dès qu'il est joignable
depuis Internet (le mot de passe circule dans l'en-tête HTTP Basic).

## Choisir

| Situation | Méthode |
|---|---|
| Je m'entraîne sur mon PC | [A. Lancement local](#a-lancement-local-sans-docker) (aucun mot de passe nécessaire) |
| Mon PC, mais isolé dans un conteneur | [B. Docker en local](#b-docker-en-local) |
| Un VPS, accès depuis plusieurs appareils | [C. VPS avec HTTPS](#c-vps-avec-https-recommandé) |
| Un VPS sans nom de domaine | [D. VPS via SSH ou Tailscale](#d-vps-sans-domaine-ssh-ou-tailscale) |

## A. Lancement local (sans Docker)

Prérequis : Node 22, Python 3.11 ou plus. Facultatif : `espeak-ng` (audio des leçons), Ollama avec `qwen3:14b` (indices).

```bash
cd questforge
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" httpx websockets pydantic
npm install
PATH="$PWD/.venv/bin:$PATH" npm run dev      # http://localhost:3000
```

Le relais lance `python3 -m uvicorn` : le venv doit être dans le `PATH`, sinon le backend ne trouve pas ses dépendances.
Sans `QUESTFORGE_PASSWORD`, le serveur n'écoute que sur `127.0.0.1`.
Pour l'ouvrir à votre réseau local (téléphone, tablette) : `QUESTFORGE_PASSWORD=... npm run dev`.

## B. Docker en local

```bash
cp .env.example .env          # puis renseigner QUESTFORGE_PASSWORD (openssl rand -base64 24)
docker compose up -d --build  # http://127.0.0.1:3000
```

## C. VPS avec HTTPS (recommandé)

Prérequis : un VPS Linux avec Docker et le plugin Compose, un nom de domaine dont l'enregistrement A pointe vers l'IP du VPS.

```bash
git clone https://github.com/Teambull31/Formation.git && cd Formation/questforge
git checkout claude/ecstatic-sagan-9wq8qv    # la branche déployée
cp .env.example .env
```

Renseigner dans `.env` : `QUESTFORGE_PASSWORD` (`openssl rand -base64 24`) et `DOMAIN` (par exemple `formation.exemple.fr`).

```bash
# pare-feu : seulement SSH, HTTP et HTTPS
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable

COMPOSE_PROFILES=https docker compose up -d --build
scripts/smoke.sh https://formation.exemple.fr "$(grep ^QUESTFORGE_PASSWORD= .env | cut -d= -f2- | tr -d '"')"
```

Caddy obtient le certificat tout seul. Le conteneur QuestForge n'est joignable que par Caddy
(`BIND_ADDRESS=127.0.0.1` : n'ouvrez jamais le port 3000 directement).

**Mise à jour** : `COMPOSE_PROFILES=https scripts/update.sh` (récupère le code, reconstruit, relance, teste).
**Sauvegarde** : `scripts/backup.sh` (progression et dossier de travail dans `backups/`, à copier hors du VPS).
**Journaux** : `docker compose logs -f questforge`.
**Changer le mot de passe** : modifier `.env`, puis `docker compose up -d`.

## D. VPS sans domaine (SSH ou Tailscale)

Sans HTTPS public, ne publiez pas le port. Gardez `BIND_ADDRESS=127.0.0.1` (défaut), puis :

```bash
docker compose up -d --build
ssh -L 3000:127.0.0.1:3000 utilisateur@mon-vps       # puis http://localhost:3000 sur votre PC
```

Avec Tailscale, mettez `BIND_ADDRESS` à l'adresse Tailscale du VPS : le trafic est chiffré par le réseau privé.

## Ce qui est protégé, et les limites

- Le relais Node authentifie (HTTP Basic, comparaison à temps constant, blocage 15 min après 10 échecs par adresse)
  et marque les requêtes validées avec un secret interne aléatoire. Le backend n'accepte le terminal, les
  vérifications de TP, les boss et l'import de module que s'ils portent ce secret, ou viennent directement de la machine.
- Le backend n'écoute que sur `127.0.0.1` dans le conteneur. Ni le mot de passe ni le secret interne ne sont
  visibles depuis le terminal ou les scripts de TP.
- Le conteneur tourne sans privilèges (utilisateur non root, `cap_drop: ALL`, `no-new-privileges`, 1 Go de mémoire, 256 processus).
- **Un seul utilisateur.** Quiconque connaît le mot de passe obtient un shell dans le conteneur : ne le partagez pas.
  Un shell dans le conteneur ne donne pas accès au système du VPS, mais il peut lire ce que contient le conteneur.
- Les fonctions annexes (War Room, Duels, Ligues…) restent des contenus embarqués dans le navigateur, sans IA ni serveur.

## Vérifier un déploiement

```bash
scripts/smoke.sh <url> <mot-de-passe>     # santé, mot de passe exigé, quête, parcours, boss, vérification d'un TP
```

Jeu de tests complet (à lancer avant de déployer une modification) :

```bash
npx tsc --noEmit && npm test
cd backend && uv run --with pytest --with fastapi --with httpx --with websockets --with pydantic pytest -q
```

Un seul test échoue sur une machine sans `espeak-ng` (`test_audio`) : c'est attendu.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| `docker compose` : « Définissez QUESTFORGE_PASSWORD » | `.env` absent ou mot de passe vide |
| Le serveur s'arrête : « exposerait le terminal au réseau » | `HOST` ouvert sans `QUESTFORGE_PASSWORD` |
| `/healthz` répond 503 | le backend Python n'a pas démarré : `docker compose logs questforge` |
| 429 après plusieurs essais | trop d'échecs de mot de passe : attendre 15 minutes |
| Audio : « synthèse vocale indisponible » | `espeak-ng` absent (inclus dans l'image Docker) |
| Le module importé disparaît | `content/` doit être le volume monté (`./content`), pas celui de l'image |
| Caddy n'obtient pas de certificat | le domaine ne pointe pas vers le VPS, ou les ports 80/443 sont fermés |

## À vérifier au premier déploiement

L'image Docker n'a pas pu être construite dans l'environnement de développement (pas de démon Docker). Les fichiers
copiés par le `Dockerfile` ont été validés en simulant leur disposition (`scripts/smoke.sh` passe), et `docker compose config`
valide le fichier Compose, mais le premier `docker compose up --build` reste à confirmer : si l'étape échoue, corrigez-la
et relancez `scripts/smoke.sh`.
