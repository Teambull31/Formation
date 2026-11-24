# Cache, couches et build multi-stage

Un build de dix minutes à chaque modification d'une ligne de code, c'est un build mal écrit. Tout se joue dans la façon dont Docker met en cache les **couches**.

## Une instruction, une couche

Chaque instruction `RUN`, `COPY` ou `ADD` crée une **couche**. Docker garde ces couches en cache : si une instruction et tout ce qui la précède n'ont pas changé, il réutilise la couche. Dès qu'une couche change, toutes les suivantes sont reconstruites.

Imaginez une pile d'assiettes : pour changer celle du milieu, il faut retirer et reposer toutes celles du dessus. On place donc **en bas** ce qui change rarement, et **en haut** ce qui change souvent.

## Les dépendances d'abord, le code ensuite

Votre code change à chaque commit ; vos dépendances, rarement. On copie donc d'abord le seul fichier de dépendances, on installe, puis on copie le reste.

```dockerfile
# FAUX : tout le code est copié avant l'installation
COPY . .                                          # change à chaque commit…
RUN pip install --no-cache-dir -r requirements.txt   # …donc réinstalle tout à chaque fois

# JUSTE : le fichier de dépendances seul, puis l'installation, puis le code
COPY requirements.txt .                           # change rarement : couche en cache
RUN pip install --no-cache-dir -r requirements.txt   # réutilisée tant que requirements.txt ne bouge pas
COPY . .                                          # seule cette couche est refaite à chaque commit
```

Si seul le code change, Docker réutilise la couche des dépendances et le build prend quelques secondes. Avec `COPY . .` placé avant `pip install`, la moindre modification du code relance toute l'installation.

!!Placez COPY . . après l'installation des dépendances, jamais avant!!

`--no-cache-dir` demande à pip de ne pas garder son cache de téléchargement dans l'image : de la place gagnée, pour rien perdu.

## Nettoyer dans la même couche

Une couche ne supprime rien des couches précédentes : un fichier effacé dans un `RUN` ultérieur occupe toujours sa place dans l'image. Le nettoyage se fait donc dans le **même** `RUN` que l'installation :

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
```

Lecture ligne par ligne :

- `\` en fin de ligne continue la même instruction sur la ligne suivante : c'est un seul `RUN`, donc une seule couche.
- `&&` enchaîne les commandes et arrête tout si l'une échoue.
- L'espace avant `&&` en début de ligne n'est que de la mise en page, pour aligner les commandes.
- `rm -rf /var/lib/apt/lists/*` supprime l'index des paquets, inutile une fois l'installation finie.

!!Séparer apt-get update et apt-get install dans deux RUN fige un index de paquets périmé dans le cache!!

## Le fichier .dockerignore

`COPY . .` copie tout le dossier, y compris `.git`, les caches Python et le fichier `.env` qui contient vos secrets. Le fichier **.dockerignore** liste ce qu'il faut exclure du contexte de build, comme un `.gitignore`.

Il se place à la racine du contexte, **à côté du Dockerfile**. Une règle par ligne :

```
# Fichier : .dockerignore
.git
.env
__pycache__
*.pyc
```

!!Un fichier .env copié dans l'image part avec elle dans tous les registres!!

## Le build multi-stage

Pour installer des dépendances, il faut parfois des outils de compilation inutiles à l'exécution. Un build **multi-stage** utilise plusieurs `FROM` : une étape de build, puis une étape finale qui ne récupère que le résultat avec `COPY --from=build`. Tout le reste est jeté, l'image finale est plus petite et expose moins de logiciels à attaquer.

Voici le Dockerfile complet. Chaque `FROM` ouvre une nouvelle étape et repart d'un système vide.

```dockerfile
# ── Étape 1 : build ───────────────────────────────────────
FROM python:3.12-slim AS build       # « AS build » nomme l'étape pour la citer plus bas
WORKDIR /app
COPY requirements.txt .              # seul, pour profiter du cache
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
#                              └─ installe dans /install, un dossier facile à récupérer en bloc

# ── Étape 2 : image finale ────────────────────────────────
FROM python:3.12-slim                # repart de zéro : rien de l'étape 1 n'est gardé…
WORKDIR /app
COPY --from=build /install /usr/local    # …sauf ce qu'on copie explicitement
COPY . .                             # le code, en dernier : il change le plus souvent
CMD ["python", "app.py"]
```

Pourquoi `--prefix=/install` puis `/usr/local` ? Pip installe d'habitude dans `/usr/local`, où vivent aussi les fichiers de Python lui-même. Avec `--prefix=/install`, seuls vos paquets atterrissent dans `/install`. L'étape finale les recopie dans `/usr/local`, là où Python les cherche.

## Pas à pas : accélérer et alléger le build

1. Repérez la ligne `COPY . .` et la ligne `pip install` du Dockerfile actuel.
2. Ajoutez ` AS build` au premier `FROM`.
3. Juste après `WORKDIR`, écrivez `COPY requirements.txt .`, puis le `RUN pip install --no-cache-dir --prefix=/install -r requirements.txt`.
4. Ajoutez une seconde étape : un nouveau `FROM python:3.12-slim`, puis `WORKDIR /app`.
5. Dans cette étape, écrivez `COPY --from=build /install /usr/local`, puis `COPY . .`, puis le `CMD`.
6. Créez `.dockerignore` à côté du Dockerfile, avec `.git`, `.env` et `__pycache__`.
7. Construisez deux fois : `docker build -t monapp:2 .`. Au second build, les étapes affichent `CACHED`.
8. Modifiez une ligne de `app.py`, reconstruisez : seule la couche `COPY . .` est refaite.
9. Comparez les tailles avec `docker images monapp`.

**À retenir :** dépendances avant le code, nettoyage dans le même RUN, .dockerignore à côté du Dockerfile, multi-stage avec `AS build` et `COPY --from=build` pour livrer une image minimale.
