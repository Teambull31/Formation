# Déploiement

> **Avertissement : vérification partielle.** `docker compose` n'est pas installé sur la machine de développement :
> `docker-compose.yml`, le profil `https` (Caddy) et `scripts/update.sh` n'ont **jamais été exécutés**, et
> `BACKUP_DOCKER=1` non plus. Le `Dockerfile` a été construit et lancé avec **podman** (émulation de la commande `docker`,
> pas Docker lui-même) ; le HEALTHCHECK y est ignoré (format OCI). Les tests Python et `scripts/smoke.sh` ont été exécutés
> contre uvicorn local et contre ce conteneur. Faites un premier essai sur une machine jetable avant de compter dessus.

## Choisir son mode

| Mode | Quand | Mot de passe | Terminal et TP |
|------|-------|--------------|----------------|
| **PC (natif)** | usage quotidien sur votre machine | inutile | oui (boucle locale) |
| **PC ou VPS + Tailscale** | accès depuis vos autres appareils | recommandé | oui avec `FORMATION_REMOTE_EXEC=1` |
| **VPS public + HTTPS** | accès depuis n'importe où | **obligatoire** | seulement avec `FORMATION_REMOTE_EXEC=1` (dangereux) |

### PC, sans Docker

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && uv run uvicorn app.main:app_factory --factory --host 127.0.0.1 --port 8000
```

Sans `FORMATION_PASSWORD`, le comportement est celui de toujours : tout est ouvert, mais le terminal et les TP
n'acceptent que la machine locale.

### Docker (PC ou VPS)

```bash
cp .env.example .env        # puis éditer : FORMATION_PASSWORD (12 caractères minimum)
docker compose up -d --build
```

L'appli écoute sur `127.0.0.1:8000` uniquement. Les données (base SQLite, dossier de travail des TP) vivent dans
le volume `formation-data` (`/data`). Le dossier `./content` est monté pour les imports hebdomadaires :
il doit appartenir à l'utilisateur `APP_UID` (par défaut 1000 ; `id -u`).

**Point d'attention : terminal et TP dans Docker.** L'appli voit l'adresse de la passerelle Docker et non `127.0.0.1`,
donc elle les refuse par défaut (403), même depuis votre PC. Pour les utiliser, activez `FORMATION_REMOTE_EXEC=1`
(voir plus bas) avec `FORMATION_ALLOWED_HOSTS=localhost,127.0.0.1`. Sans cela, cours, QCM, révisions, gacha et
progression fonctionnent, pas les TP ni le boss.

## Mot de passe

`FORMATION_PASSWORD` (12 caractères minimum, sinon l'appli refuse de démarrer) active une authentification
HTTP Basic sur **toutes** les routes, WebSocket comprise : n'importe quel nom d'utilisateur, seul le mot de passe compte.
Le navigateur le mémorise. Générez-le avec `openssl rand -base64 24`. Il n'est jamais écrit dans les journaux ni
dans les réponses. Sans HTTPS, il circule en clair : n'exposez jamais l'appli en HTTP sur Internet.

## HTTPS (VPS public)

1. Faites pointer un nom de domaine vers l'IP du serveur ; ouvrez les ports 80 et 443.
2. Dans `.env` : `DOMAIN=formation.exemple.fr` et `FORMATION_PASSWORD=...`.
3. `docker compose --profile https up -d --build` : Caddy obtient et renouvelle le certificat Let's Encrypt.

L'appli reste sur `127.0.0.1:8000` ; seul Caddy est exposé.

## Tailscale (option déjà utilisée)

Le plus sûr pour un accès personnel : ne publiez rien sur Internet. Installez Tailscale sur le serveur et sur vos
appareils, puis soit :

- `BIND_ADDRESS=<adresse 100.x du serveur>` dans `.env` (l'appli n'écoute que sur le réseau Tailscale), soit
- `tailscale serve --bg 8000` pour un HTTPS `https://machine.tailnet.ts.net` géré par Tailscale.

Si vous voulez terminal et TP à distance, `FORMATION_ALLOWED_HOSTS` doit contenir le nom utilisé dans l'URL
(par exemple `machine.tailnet.ts.net` ou l'adresse `100.x`).

## FORMATION_REMOTE_EXEC : danger

Par défaut, le terminal, le lancement et la vérification des TP, le boss, l'import hebdomadaire et les indices
restent réservés à la machine locale, **même avec un mot de passe valide**.

`FORMATION_REMOTE_EXEC=1` lève cette limite : quiconque connaît le mot de passe obtient **un shell sur le serveur**
(avec les droits de l'utilisateur de l'appli) et peut lire ou détruire tout ce que ce compte voit. À n'activer que
si :

- `FORMATION_PASSWORD` est long et unique (l'appli refuse de démarrer sans) ;
- `FORMATION_ALLOWED_HOSTS` liste exactement les noms utilisés (obligatoire) : l'en-tête `Host` et l'`Origin` doivent y figurer ;
- l'accès passe par HTTPS ou Tailscale, jamais en HTTP clair ;
- le serveur ne contient rien de précieux (de préférence un VPS dédié) ; le conteneur est sans privilèges
  (`cap_drop: ALL`, `no-new-privileges`, utilisateur non root) mais son réseau sortant est libre.

Aucune limitation de tentatives de mot de passe n'est implémentée : choisissez un mot de passe fort.

## Sauvegarde

```bash
BACKUP_DOCKER=1 scripts/backup.sh ./backups   # conteneur Docker
scripts/backup.sh ./backups                   # installation native (~/.formation ou FORMATION_DB / FORMATION_WORKSPACE)
```

Produit `formation-AAAAMMJJ-HHMMSS.db` (copie cohérente de la base) et `workspace-AAAAMMJJ-HHMMSS.tgz`.
Copiez-les hors du serveur. Pour restaurer : arrêtez l'appli et remplacez `formation.db`.
Pensez aussi à sauvegarder `./content` si vous importez des modules.

## Mise à jour

```bash
scripts/update.sh        # git pull --ff-only, reconstruction, redémarrage, test de fumée
```

## Test de fumée

```bash
SMOKE_PASSWORD='mot-de-passe' scripts/smoke.sh http://127.0.0.1:8000   # évite le mot de passe dans les arguments
```

Vérifie `/`, `/manifest.webmanifest`, `/api/quest`, le refus (401) sans mot de passe, et qu'un démarrage de TP
avec un `Host` non autorisé est refusé (403), que `FORMATION_REMOTE_EXEC` soit actif ou non. Ce dernier contrôle
n'a de sens que sur l'URL directe de l'appli, pas derrière Caddy. Le mot de passe n'apparaît ni dans la liste des
processus ni dans la sortie.
