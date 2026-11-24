# Images, conteneurs et premier Dockerfile

« Ça marche sur ma machine » : la phrase que Docker veut faire disparaître. Un conteneur embarque l'application avec ses dépendances, et tourne de la même façon partout.

## Image et conteneur

Une **image** est un modèle figé, en lecture seule : le système de base, vos fichiers, la commande de démarrage. Un **conteneur** est une instance en cours d'exécution d'une image. De la même image, on lance autant de conteneurs qu'on veut. Un conteneur n'est pas une machine virtuelle : il partage le noyau de l'hôte et n'isole que les processus, le réseau et les fichiers.

Comparaison utile : l'image est la classe, le conteneur est l'objet. Ou encore : l'image est le fichier `.iso`, le conteneur est la machine démarrée dessus.

!!Un conteneur supprimé perd tout ce qu'il a écrit : les données qui comptent vont dans un volume!!

## Le Dockerfile : la recette de l'image

Un **Dockerfile** est un fichier texte, une instruction par ligne. `docker build` le lit **de haut en bas** et produit l'image. Il n'y a pas d'indentation : l'ordre des lignes est la seule structure, et chaque ligne s'appuie sur l'état laissé par la précédente.

```dockerfile
# Fichier : Dockerfile (à la racine du projet, sans extension)
FROM python:3.12-slim          # 1. TOUJOURS en premier : le système de départ
WORKDIR /app                   # 2. avant COPY : crée /app et s'y place
COPY app.py .                  # 3. « . » = le WORKDIR, donc /app/app.py
EXPOSE 8000                    # 4. documente le port ; n'ouvre rien
CMD ["python", "app.py"]       # 5. TOUJOURS à la fin : ce qui tourne au démarrage
```

Pourquoi cet ordre :

1. `FROM` choisit l'image de départ. Aucune instruction ne peut le précéder (sauf `ARG`) : il n'y a encore aucun système de fichiers.
2. `WORKDIR` fixe le dossier de travail. Placé avant `COPY`, il donne un sens au `.` de destination. Sans lui, le fichier atterrit à la racine `/`, mélangé au système.
3. `COPY` copie des fichiers du dossier local (le **contexte de build**) vers l'image. Le premier argument est relatif au dossier où vous lancez `docker build`, le second est relatif au `WORKDIR`.
4. `EXPOSE` documente le port d'écoute, sans l'ouvrir. Il informe les lecteurs et les outils.
5. `CMD` donne la commande lancée au démarrage. Il n'est exécuté qu'au `docker run`, pas pendant le build : on le met à la fin, par convention et pour la lisibilité.

## Épingler la version de base

`python:latest` désigne « la dernière version », qui change sans prévenir : le build de lundi ne ressemble plus à celui de vendredi. Un tag précis comme `python:3.12-slim` rend le build **reproductible**. La variante `slim` est plus petite que l'image complète.

Un tag se lit ainsi : `python` est le nom de l'image, ce qui suit `:` est la version. `3.12-slim` veut dire « Python 3.12, variante allégée ». Pour figer encore plus, on peut écrire `python:3.12.7-slim`.

!!N'utilisez jamais le tag latest dans un Dockerfile de production!!

## CMD en forme exec

`CMD ["python", "app.py"]` est la forme **exec** : une liste JSON, sans shell intermédiaire. Le processus de l'application est alors le processus principal du conteneur et reçoit directement les signaux d'arrêt. La forme texte `CMD python app.py` passe par un shell, qui peut avaler le signal `SIGTERM` et retarder l'arrêt.

```dockerfile
# FAUX : forme shell, /bin/sh devient le processus principal
CMD python app.py

# FAUX : guillemets simples, ce n'est pas du JSON ; Docker retombe en forme shell
CMD ['python', 'app.py']

# JUSTE : forme exec, chaque mot est un élément de la liste
CMD ["python", "app.py"]
```

Chaque argument est un élément séparé : `["python", "app.py", "--port", "8000"]`, jamais `["python app.py"]`.

!!Les guillemets d'une liste JSON sont obligatoirement doubles!!

## Les commandes de base

`docker build -t monapp:1.0 .` construit l'image. `docker run -p 8000:8000 monapp:1.0` lance un conteneur et relie le port 8000 de la machine à celui du conteneur. `docker ps` liste les conteneurs en cours, `docker logs` affiche leur sortie.

Décomposition de la commande de build :

```bash
docker build -t monapp:1.0 .
#            │  │          └─ le contexte : ce dossier est envoyé à Docker, COPY y puise
#            │  └─ nom:version donnés à l'image
#            └─ -t = tag
```

Et de la commande de lancement :

```bash
docker run -d --name web -p 8000:8000 monapp:1.0
#          │  │          │    │    └─ port DANS le conteneur (celui d'EXPOSE)
#          │  │          │    └─ port sur VOTRE machine
#          │  │          └─ -p = publier un port
#          │  └─ nom du conteneur, pour docker logs web, docker stop web
#          └─ -d = en arrière-plan
```

## Pas à pas : votre premier Dockerfile

1. À la racine du projet, à côté de `app.py`, créez un fichier nommé exactement `Dockerfile`.
2. Ligne 1 : `FROM python:3.12-slim`.
3. Ligne 2 : `WORKDIR /app`, chemin absolu (il commence par `/`).
4. Ligne 3 : `COPY app.py .`.
5. Ligne 4 : `EXPOSE 8000`, le port sur lequel `app.py` écoute.
6. Ligne 5 : `CMD ["python", "app.py"]`, guillemets doubles.
7. Construisez : `docker build -t monapp:1.0 .`. Chaque ligne du Dockerfile apparaît comme une étape `[n/5]`.
8. Lancez : `docker run -d --name web -p 8000:8000 monapp:1.0`, puis `curl localhost:8000`.
9. Lisez la sortie avec `docker logs web`, puis arrêtez avec `docker stop web && docker rm web`.

**À retenir :** image contre conteneur, Dockerfile lu de haut en bas, `FROM` en premier et `CMD` en dernier, version épinglée, CMD en forme exec, données dans des volumes.
