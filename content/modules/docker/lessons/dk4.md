# Répare la panne : la pile qui ne repart pas

Un conteneur qui ne démarre pas ne dit presque rien : il s'arrête. Cette leçon donne les **commandes de diagnostic** et les familles de pannes, puis le TP vous met devant une pile entière à réparer.

## Les quatre questions

1. **Le build passe-t-il ?** `docker compose build` montre l'étape qui casse.
2. **Le conteneur tourne-t-il ?** `docker compose ps -a` : `Up`, `Exited (code)`, `Restarting`.
3. **Que dit-il ?** `docker compose logs <service>` : la dernière ligne avant l'arrêt.
4. **Est-il joignable ?** `curl` depuis l'hôte, puis depuis l'intérieur avec `docker compose exec`.

Comparer l'intérieur et l'extérieur est le geste clé : si ça répond dedans et pas dehors, le problème est **réseau**, pas applicatif.

## Lire un code de sortie

| Code | Signification | Piste |
|---|---|---|
| `0` | le processus a fini normalement | un CMD qui n'est pas un serveur |
| `1` | erreur de l'application | les journaux |
| `126` / `127` | commande non exécutable ou introuvable | chemin du CMD, droits |
| `137` | tué par SIGKILL | mémoire (`OOMKilled`) ou `docker kill` |
| `143` | SIGTERM | arrêt demandé |

`docker inspect <conteneur> --format '{{.State.OOMKilled}}'` tranche entre mémoire et arrêt manuel.

!!Augmenter la mémoire sans regarder la consommation réelle cache une fuite : docker stats d'abord!!

## Les familles de pannes

- **contexte** : `COPY ... not found` alors que le fichier existe. Un motif de `.dockerignore` le retire du contexte.
- **écoute** : l'application écoute sur `127.0.0.1` dans le conteneur. Il faut `0.0.0.0`.
- **mémoire** : code 137 et `OOMKilled: true`.
- **volume** : données perdues après `down` puis `up`. Elles vivaient dans la couche du conteneur.
- **version** : rien n'a changé chez vous mais tout casse après un `pull`. Une image `latest` a été republiée.

!!docker compose down -v supprime aussi les volumes nommés : sur une base, c'est la perte des données!!

## Inspecter sans deviner

```bash
docker compose ps -a
docker compose logs --tail 50 api
docker inspect shop-worker --format '{{.State.ExitCode}} {{.State.OOMKilled}}'
docker compose exec api sh -c 'ss -ltnp || netstat -ltn'
docker volume ls
docker image inspect nginx:1.27.2 --format '{{.Created}}'
docker compose config        # le fichier tel que Compose le comprend
```

`docker compose config` est souvent oublié : il montre l'indentation et les variables comme Compose les lit.

!!Ne lancez jamais un conteneur en privileged pour « voir si ça marche » : c'est donner la machine entière!!

## Labo réel

Si Docker est installé, rejouez le TP pour de vrai :

```bash
docker compose build && docker compose up -d
docker compose ps -a
curl -s http://127.0.0.1:8000/health
docker compose down && docker compose up -d && docker volume ls
```

**À retenir :** build, état, journaux, joignabilité ; comparer dedans et dehors ; 137 = SIGKILL, souvent la mémoire ; `.dockerignore` peut cacher un fichier au build ; `0.0.0.0` dans le conteneur ; un volume pour les données ; jamais `latest` ; `docker compose config` pour voir ce que Compose comprend.
