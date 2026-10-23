# Images, conteneurs et premier Dockerfile

« Ça marche sur ma machine » : la phrase que Docker veut faire disparaître. Un conteneur embarque l'application avec ses dépendances, et tourne de la même façon partout.

## Image et conteneur

Une **image** est un modèle figé, en lecture seule : le système de base, vos fichiers, la commande de démarrage. Un **conteneur** est une instance en cours d'exécution d'une image. De la même image, on lance autant de conteneurs qu'on veut. Un conteneur n'est pas une machine virtuelle : il partage le noyau de l'hôte et n'isole que les processus, le réseau et les fichiers.

!!Un conteneur supprimé perd tout ce qu'il a écrit : les données qui comptent vont dans un volume!!

## Le Dockerfile : la recette de l'image

Un **Dockerfile** est un fichier texte, une instruction par ligne. `docker build` le lit et produit l'image.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
```

`FROM` choisit l'image de départ. `WORKDIR` fixe le dossier de travail. `COPY` copie des fichiers du dossier local vers l'image. `EXPOSE` documente le port d'écoute, sans l'ouvrir. `CMD` donne la commande lancée au démarrage.

## Épingler la version de base

`python:latest` désigne « la dernière version », qui change sans prévenir : le build de lundi ne ressemble plus à celui de vendredi. Un tag précis comme `python:3.12-slim` rend le build **reproductible**. La variante `slim` est plus petite que l'image complète.

!!N'utilisez jamais le tag latest dans un Dockerfile de production!!

## CMD en forme exec

`CMD ["python", "app.py"]` est la forme **exec** : une liste JSON, sans shell intermédiaire. Le processus de l'application est alors le processus principal du conteneur et reçoit directement les signaux d'arrêt. La forme texte `CMD python app.py` passe par un shell, qui peut avaler le signal `SIGTERM` et retarder l'arrêt.

!!Les guillemets d'une liste JSON sont obligatoirement doubles!!

## Les commandes de base

`docker build -t monapp:1.0 .` construit l'image. `docker run -p 8000:8000 monapp:1.0` lance un conteneur et relie le port 8000 de la machine à celui du conteneur. `docker ps` liste les conteneurs en cours, `docker logs` affiche leur sortie.

**À retenir :** image contre conteneur, Dockerfile reproductible, version épinglée, CMD en forme exec, données dans des volumes.
