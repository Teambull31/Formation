# Projet fil rouge : l'image et sa publication

L'étape 2 transforme le code testé en **artefact** : une image Docker durcie, construite et publiée par la CI, étiquetée par le commit. C'est cette image exacte que Kubernetes déploiera.

## Le Dockerfile du projet

- Une première étape installe les dépendances (`pip install --prefix=/install`).
- L'image finale copie ce résultat et `app/`, rien d'autre.
- Un utilisateur **non-root** créé avec `useradd`, et `USER` avant le `CMD`.
- `HEALTHCHECK` qui appelle `/healthz`.
- `CMD ["python", "-m", "app.main"]` en forme exec, pour recevoir SIGTERM.

`.dockerignore` retire `.git`, `.env` et les caches du contexte de build.

!!Un .env oublié dans le contexte de build finit dans une couche de l'image, lisible par quiconque la télécharge!!

## Publier sur ghcr.io

Le registre de GitHub accepte le `GITHUB_TOKEN` du workflow : aucun secret à créer. Le job `image` :

1. attend `test` (`needs: [test]`) ;
2. ne tourne que sur `main` : une pull request ne publie rien ;
3. reçoit `packages: write` à lui seul ;
4. construit et pousse `ghcr.io/<compte>/commandes:${GITHUB_SHA}`.

L'étiquette par **SHA du commit** dit exactement quel code tourne. Le retour arrière devient « redéployer le SHA précédent ».

!!Publier latest depuis la CI rend tout retour arrière incertain : personne ne sait ce que latest contenait hier!!

## Vérifier l'image

```bash
docker build -t commandes .
docker run --rm -d --name commandes -p 127.0.0.1:8000:8000 commandes
docker inspect commandes --format '{{.Config.User}} {{.State.Health.Status}}'
docker image history commandes
```

`docker image history` montre la taille de chaque couche : l'image finale doit faire environ 150 Mo, pas 1 Go.

!!Ne donnez jamais packages: write au niveau du workflow : chaque job, y compris ceux des pull requests, pourrait publier!!

## Labo réel

```bash
git add Dockerfile .dockerignore .github && git commit -m "feat: image publiée par la ci" && git push
gh run watch
docker pull ghcr.io/<compte>/commandes:$(git rev-parse HEAD)
```

**À retenir :** multi-stage, non-root, `HEALTHCHECK`, `CMD` exec ; `.dockerignore` ; publication sur `main` seulement, `packages: write` au seul job `image` ; étiquette par SHA, jamais `latest`.
