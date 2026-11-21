# Fiche de révision : Docker

## Image et conteneur

- **Image** : modèle en lecture seule, empilement de couches, identifié par `nom:tag` ou `@sha256:...`.
- **Conteneur** : une image en cours d'exécution, avec sa couche inscriptible, jetable.
- **Registre** : stockage des images (Docker Hub, GHCR, registre privé).
- Les données durables vont dans un **volume**, jamais dans le conteneur.

## Commandes

```bash
docker build -t app:1.0 .
docker run -d --name app -p 127.0.0.1:8000:8000 app:1.0
docker ps -a
docker logs -f app
docker exec -it app sh
docker stop app && docker rm app
docker images
docker image history app:1.0     # taille de chaque couche
docker inspect app
docker volume create data
docker compose up -d && docker compose logs -f
docker system prune              # avec prudence
```

## Dockerfile de référence

```dockerfile
FROM python:3.12.7-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12.7-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY app.py .
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "app.py"]
```

## Règles d'or

- Image de base avec **version précise**, jamais `latest`.
- `WORKDIR` absolu ; `COPY` plutôt que `ADD`.
- Dépendances **avant** le code : le cache des couches évite de tout réinstaller.
- Installation et nettoyage dans le **même** `RUN` (`apt-get install ... && rm -rf /var/lib/apt/lists/*`).
- `.dockerignore` : `.git`, `.env`, `__pycache__`, `node_modules`.
- **Multi-stage** : outils de build dans la première étape, image finale minimale.
- `CMD` en forme **exec** (`["python", "app.py"]`) : le processus reçoit SIGTERM et s'arrête proprement.
- `USER` non-root.
- !!Un secret copié dans une couche reste lisible dans l'image, même supprimé par une instruction suivante!!

## Exécution durcie (compose)

```yaml
services:
  app:
    image: app:1.0
    ports: ["127.0.0.1:8000:8000"]
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    env_file: .env
    restart: unless-stopped
```

- Port lié à `127.0.0.1` si seul un proxy local doit y accéder.
- !!Monter /var/run/docker.sock dans un conteneur lui donne le contrôle de la machine!!
- Secrets à l'exécution (`env_file` hors Git, secrets compose), pas dans l'image.

## Dépannage

- Le conteneur s'arrête tout de suite : `docker logs <id>` ; le processus principal s'est terminé.
- Code `137` : tué (mémoire ou `docker kill`) ; `143` : SIGTERM.
- Port injoignable : l'application écoute sur `127.0.0.1` **dans** le conteneur au lieu de `0.0.0.0`.
- Image trop grosse : `docker image history`, passer en multi-stage et `-slim`.
- Build qui réinstalle tout à chaque modification : `COPY . .` placé avant l'installation des dépendances.

## Questions d'entretien

- Différence entre image et conteneur ?
- Pourquoi un build multi-stage ?
- CMD forme shell ou exec : conséquence sur l'arrêt ?
- Comment garder une image légère et sûre ?
