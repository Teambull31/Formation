# Sécurité : non-root, secrets et durcissement

Un conteneur n'est pas une boîte étanche. Une application compromise dans un conteneur mal configuré donne souvent un accès complet à la machine hôte.

## Le Dockerfile durci, en entier

Voici le Dockerfile d'arrivée. Les commentaires disent pourquoi chaque ligne de sécurité est à cet endroit précis.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt    # besoin de root : AVANT USER
COPY . .
RUN useradd --uid 1000 --create-home app              # crée le compte : besoin de root
USER app                                              # ← à partir d'ici, plus de root
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')"]
CMD ["python", "app.py"]                              # lancé en tant que app
# Aucune ligne ENV ou ARG avec un mot de passe : il arrive à l'exécution
```

## Ne pas tourner en root

Par défaut, le processus d'un conteneur est **root**. Si une faille permet de s'échapper, l'attaquant est root sur l'hôte. On crée donc un utilisateur sans privilèges et on l'active avec `USER`, après les étapes qui ont besoin de droits (installation, copie).

L'ordre est imposé par la logique : `useradd` modifie `/etc/passwd`, ce qu'un compte ordinaire ne peut pas faire. Il vient donc **avant** `USER`. Si vous écrivez `USER app` avant `RUN pip install`, l'installation échoue faute de droits.

```dockerfile
# FAUX : USER trop tôt, l'installation n'a plus les droits
USER app
RUN pip install -r requirements.txt     # Permission denied

# JUSTE : on installe en root, puis on bascule
RUN pip install -r requirements.txt
RUN useradd --uid 1000 --create-home app
USER app
```

!!Tout ce qui est écrit après USER s'exécute sans droits root : placez-le après les installations!!

## Jamais de secret dans l'image

Un `ENV DB_PASSWORD=hunter2` ou un `ARG` secret reste lisible dans l'image avec `docker history`, et dans tous les registres où elle part. Un **secret** se fournit à l'exécution : variable d'environnement passée au lancement, fichier monté, ou gestionnaire de secrets. Dans un fichier compose, on écrit `${DB_PASSWORD}` et la valeur vit dans un fichier `.env` que Git ne versionne pas.

Le trajet du secret, de bout en bout :

```
# Fichier : .env  (à côté de docker-compose.yml, listé dans .gitignore ET .dockerignore)
DB_PASSWORD=une-valeur-longue-et-aleatoire
```

```yaml
# Fichier : docker-compose.yml
services:
  web:
    environment:
      DB_PASSWORD: ${DB_PASSWORD}     # Compose remplace par la valeur lue dans .env
```

L'application lit ensuite `os.environ["DB_PASSWORD"]`. La valeur n'est jamais dans l'image, ni dans Git.

!!Un secret écrit dans un Dockerfile doit être considéré comme public, même après suppression du fichier!!

## Le healthcheck

L'instruction **HEALTHCHECK** lance régulièrement une commande qui dit si l'application répond vraiment. Sans elle, Docker sait que le processus tourne, pas qu'il fonctionne. Un orchestrateur peut alors redémarrer un conteneur bloqué.

Les options (`--interval`, `--timeout`) se placent **entre** `HEALTHCHECK` et `CMD`. Le `CMD` qui suit est celui du test de santé, pas celui de l'application : un Dockerfile peut donc contenir deux `CMD`, l'un dans `HEALTHCHECK`, l'autre seul. `docker ps` affiche ensuite `(healthy)` ou `(unhealthy)`.

## Durcir l'exécution avec compose

Le fichier `docker-compose.yml` retire des pouvoirs au conteneur : `cap_drop: [ALL]` supprime les **capacités** Linux (les fragments des droits de root), `read_only: true` rend son système de fichiers non modifiable, `no-new-privileges` interdit toute élévation de droits.

```yaml
# Fichier : docker-compose.yml
services:                          # niveau 0 : la liste des conteneurs
  web:                             # niveau 1 : un service, nommé librement
    build: .                       # niveau 2 : toutes les options de « web » sont ici
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
    read_only: true                # niveau 2 : option du service
    tmpfs:
      - /tmp                       # read_only bloque /tmp : on lui donne un dossier en mémoire
    cap_drop:                      # niveau 2 : une liste…
      - ALL                        # …dont chaque élément commence par un tiret (niveau 3)
    security_opt:
      - no-new-privileges:true
    ports:
      - "127.0.0.1:8000:8000"      # guillemets : sinon YAML peut mal lire les « : »
```

Toutes les options de sécurité sont au **niveau 2**, sous le nom du service. Placées au niveau 1, à côté de `web:`, Compose les prendrait pour d'autres services et refuserait le fichier.

Le préfixe `127.0.0.1:` publie le port sur la machine seule, pas sur tout le réseau. Deux réglages à ne jamais utiliser sans raison grave : `privileged: true` et le montage de `/var/run/docker.sock`, qui donnent le contrôle de l'hôte.

!!Un port publié sans préfixe est ouvert à tout le réseau, parfois à tout Internet!!

## Pas à pas : durcir l'image et son lancement

1. Dans le Dockerfile, supprimez toute ligne `ENV` ou `ARG` qui contient un mot de passe.
2. Après les `RUN pip install` et `COPY`, ajoutez `RUN useradd --uid 1000 --create-home app`, puis `USER app`.
3. Avant le `CMD`, ajoutez la ligne `HEALTHCHECK` avec son propre `CMD`.
4. Dans `docker-compose.yml`, sous le service, supprimez `privileged: true` et le volume `/var/run/docker.sock`.
5. Ajoutez au niveau 2 : `read_only: true`, `cap_drop:` avec `- ALL`, `security_opt:` avec `- no-new-privileges:true`.
6. Remplacez `"8000:8000"` par `"127.0.0.1:8000:8000"`.
7. Remplacez le mot de passe en clair par `${DB_PASSWORD}`, et créez `.env` avec la valeur.
8. Vérifiez : `docker compose config` affiche le fichier tel que Compose le comprend, avec la variable remplacée.

**À retenir :** USER non-root après les installations, secrets à l'exécution via `.env`, HEALTHCHECK, cap_drop ALL, port sur 127.0.0.1, pas de docker.sock.
