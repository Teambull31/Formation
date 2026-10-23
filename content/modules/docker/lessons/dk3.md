# Sécurité : non-root, secrets et durcissement

Un conteneur n'est pas une boîte étanche. Une application compromise dans un conteneur mal configuré donne souvent un accès complet à la machine hôte.

## Ne pas tourner en root

Par défaut, le processus d'un conteneur est **root**. Si une faille permet de s'échapper, l'attaquant est root sur l'hôte. On crée donc un utilisateur sans privilèges et on l'active avec `USER`, après les étapes qui ont besoin de droits (installation, copie).

```dockerfile
RUN useradd --uid 1000 --create-home app
USER app
```

!!Tout ce qui est écrit après USER s'exécute sans droits root : placez-le après les installations!!

## Jamais de secret dans l'image

Un `ENV DB_PASSWORD=hunter2` ou un `ARG` secret reste lisible dans l'image avec `docker history`, et dans tous les registres où elle part. Un **secret** se fournit à l'exécution : variable d'environnement passée au lancement, fichier monté, ou gestionnaire de secrets. Dans un fichier compose, on écrit `${DB_PASSWORD}` et la valeur vit dans un fichier `.env` que Git ne versionne pas.

!!Un secret écrit dans un Dockerfile doit être considéré comme public, même après suppression du fichier!!

## Le healthcheck

L'instruction **HEALTHCHECK** lance régulièrement une commande qui dit si l'application répond vraiment. Sans elle, Docker sait que le processus tourne, pas qu'il fonctionne. Un orchestrateur peut alors redémarrer un conteneur bloqué.

```dockerfile
HEALTHCHECK --interval=30s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')"]
```

## Durcir l'exécution avec compose

Le fichier `docker-compose.yml` retire des pouvoirs au conteneur : `cap_drop: [ALL]` supprime les **capacités** Linux (les fragments des droits de root), `read_only: true` rend son système de fichiers non modifiable, `no-new-privileges` interdit toute élévation de droits.

```yaml
services:
  web:
    read_only: true
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    ports:
      - "127.0.0.1:8000:8000"
```

Le préfixe `127.0.0.1:` publie le port sur la machine seule, pas sur tout le réseau. Deux réglages à ne jamais utiliser sans raison grave : `privileged: true` et le montage de `/var/run/docker.sock`, qui donnent le contrôle de l'hôte.

!!Un port publié sans préfixe est ouvert à tout le réseau, parfois à tout Internet!!

**À retenir :** USER non-root, secrets à l'exécution, HEALTHCHECK, cap_drop ALL, port sur 127.0.0.1, pas de docker.sock.
