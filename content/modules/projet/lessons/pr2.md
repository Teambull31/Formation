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

## Les fichiers commentés

```dockerfile
# Fichier : Dockerfile (racine du dépôt)
# ── Étape 1 : les dépendances ──
FROM python:3.12.7-slim AS deps            # version figée ; « deps » nomme l'étape
WORKDIR /src
COPY requirements.txt .                    # seul : la couche reste en cache
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Étape 2 : l'image livrée ──
FROM python:3.12.7-slim
WORKDIR /srv
COPY --from=deps /install /usr/local       # les paquets, sans les outils de build
COPY app/ ./app/                           # le code seul, pas tout le dépôt
RUN useradd --create-home --uid 10001 app  # en root : avant USER
USER 10001                                 # uid numérique : Kubernetes peut vérifier runAsNonRoot
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["python", "-m", "app.main"]           # forme exec ; « -m » car app est un paquet
```

Pourquoi `USER 10001` plutôt que `USER app` ? Kubernetes, à l'étape 3, vérifie `runAsNonRoot` en lisant l'identifiant. Avec un nom, il ne peut pas savoir si c'est root et refuse de démarrer le pod.

Le job `image` s'ajoute dans le **même** `ci.yml`, sous `jobs:`, au même niveau que `test:` (2 espaces) :

```yaml
jobs:
  test:
    # … inchangé …

  image:                                   # ← niveau 1 : un second job, frère de test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [test]                          # n'image que du code testé
    if: github.ref == 'refs/heads/main'    # une PR ne publie rien
    permissions:                           # ← bloc du job : remplace celui du workflow
      contents: read                       #   à répéter : le bloc du job remplace tout
      packages: write                      #   le droit de pousser sur ghcr.io
    steps:
      - uses: actions/checkout@v4
      - run: echo "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
        env:
          GH_TOKEN: ${{ github.token }}    # le jeton passe par env, jamais dans le texte du run
      - run: |                             # « | » : plusieurs commandes, une par ligne
          IMAGE="ghcr.io/${GITHUB_REPOSITORY,,}:${GITHUB_SHA}"
          docker build -t "$IMAGE" .
          docker push "$IMAGE"
```

`${GITHUB_REPOSITORY,,}` met le nom du dépôt en minuscules : ghcr.io refuse les majuscules, et `Moncompte/commandes` deviendrait une erreur au push.

## Pas à pas : l'étape 2

1. Écrivez le `Dockerfile` à la racine, étape par étape, en relisant chaque commentaire.
2. Écrivez `.dockerignore` à côté : `.git`, `.github`, `.env`, `__pycache__`.
3. Si Docker est installé : `docker build -t commandes .`, puis lancez le conteneur et appelez `/healthz`.
4. Dans `ci.yml`, ajoutez le job `image` sous `jobs:`, aligné sur `test:`.
5. Vérifiez avec `actionlint` : il signale un `needs` vers un job inexistant ou une indentation fausse.
6. Poussez sur `main` : deux jobs apparaissent, `test` puis `image`. L'image est visible dans l'onglet **Packages** de votre profil.

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
