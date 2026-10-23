# Cache, couches et build multi-stage

Un build de dix minutes à chaque modification d'une ligne de code, c'est un build mal écrit. Tout se joue dans la façon dont Docker met en cache les **couches**.

## Une instruction, une couche

Chaque instruction `RUN`, `COPY` ou `ADD` crée une **couche**. Docker garde ces couches en cache : si une instruction et tout ce qui la précède n'ont pas changé, il réutilise la couche. Dès qu'une couche change, toutes les suivantes sont reconstruites.

## Les dépendances d'abord, le code ensuite

Votre code change à chaque commit ; vos dépendances, rarement. On copie donc d'abord le seul fichier de dépendances, on installe, puis on copie le reste.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
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

!!Séparer apt-get update et apt-get install dans deux RUN fige un index de paquets périmé dans le cache!!

## Le fichier .dockerignore

`COPY . .` copie tout le dossier, y compris `.git`, les caches Python et le fichier `.env` qui contient vos secrets. Le fichier **.dockerignore** liste ce qu'il faut exclure du contexte de build, comme un `.gitignore`.

```
.git
.env
__pycache__
```

!!Un fichier .env copié dans l'image part avec elle dans tous les registres!!

## Le build multi-stage

Pour installer des dépendances, il faut parfois des outils de compilation inutiles à l'exécution. Un build **multi-stage** utilise plusieurs `FROM` : une étape de build, puis une étape finale qui ne récupère que le résultat avec `COPY --from=build`. Tout le reste est jeté, l'image finale est plus petite et expose moins de logiciels à attaquer.

**À retenir :** dépendances avant le code, nettoyage dans le même RUN, .dockerignore, multi-stage pour livrer une image minimale.
