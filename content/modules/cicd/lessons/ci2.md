# Cache, matrice et dépendances entre jobs

Un pipeline lent est un pipeline que l'on contourne. Trois mécanismes le gardent rapide sans rien sacrifier : le cache, la matrice et l'enchaînement des jobs. Deux réglages le gardent sûr et économe : les permissions du jeton et les limites de temps.

## Le fichier d'arrivée, en entier

Voici le workflow que vous allez obtenir. Lisez-le d'abord en entier : chaque section de la leçon explique ensuite un bloc, et pourquoi il est placé à cet endroit.

```yaml
# Fichier : .github/workflows/ci.yml
name: CI
on:
  push:
  pull_request:

permissions:                  # niveau 0 : vaut pour TOUS les jobs du fichier
  contents: read              # le jeton peut lire le dépôt, pas écrire

concurrency:                  # niveau 0 : règle commune à tout le workflow
  group: ci-${{ github.ref }}       # une file par branche
  cancel-in-progress: true          # un nouveau commit annule l'ancien run

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10       # niveau 2 : propriété du job, à côté de runs-on
    strategy:                 # niveau 2 : propriété du job test
      matrix:                 # niveau 3 : enfant de strategy
        python-version: ["3.11", "3.12"]   # une liste = un job par valeur
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}   # lit la valeur du job courant
          cache: pip                                     # même bloc with : paramètre de setup-python
      - run: pip install -r requirements.txt
      - run: pytest -q

  build:                      # niveau 1 : second job, au même niveau que test
    needs: test               # niveau 2 : attend la réussite de test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: python -m compileall -q .
```

Repérez les trois niveaux où l'on peut écrire un réglage :

| Niveau | Où | Portée | Exemples |
| --- | --- | --- | --- |
| Workflow | colonne 0, à côté de `on:` et `jobs:` | tout le fichier | `permissions`, `concurrency`, `env` |
| Job | sous le nom du job, à côté de `runs-on` | ce job seulement | `needs`, `strategy`, `timeout-minutes` |
| Étape | sous le tiret de l'étape | cette étape seulement | `with`, `env`, `name` |

## Le cache des dépendances

Sans **cache**, chaque exécution retélécharge toutes les dépendances. Avec `actions/setup-python`, une ligne suffit : `cache: pip` mémorise le dossier de pip, clé calculée à partir de `requirements.txt`. Le cache est invalidé quand ce fichier change.

`cache: pip` est un **paramètre de l'action** setup-python. Il va donc dans son bloc `with:`, aligné sur `python-version`. Placé ailleurs, il est ignoré ou refusé :

```yaml
# FAUX : cache est une clé de l'étape, pas un paramètre de l'action
      - uses: actions/setup-python@v5
        cache: pip
        with:
          python-version: "3.12"

# JUSTE : cache est dans with, à côté de python-version
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
```

## La matrice

Pour tester sur plusieurs versions, ne copiez pas le job : déclarez une **matrice**. GitHub crée un **job** par valeur, en **parallèle**.

La matrice est une propriété du **job**, car c'est le job entier qui est dupliqué. Elle se place donc sous `test:`, au même niveau que `runs-on` et `steps`, jamais dans une étape :

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:                              # ← niveau du job
      matrix:
        python-version: ["3.11", "3.12"]   # nom de variable libre
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}   # ← on relit la variable ici
          cache: pip
```

Le nom `python-version` sous `matrix:` est une variable que vous inventez. On la relit avec `${{ matrix.<nom> }}`. Si vous écrivez `matrix.python` alors que la matrice déclare `python-version`, la valeur est vide et setup-python échoue.

## Enchaîner les jobs

Les jobs d'un workflow tournent en parallèle par défaut. `needs: test` fait attendre un job jusqu'à la réussite du job `test` : on ne construit ou ne déploie pas ce qui n'a pas passé les tests.

`needs` se place dans le job **qui attend**, pas dans celui qu'on attend. Sa valeur est le nom du job, exactement comme écrit sous `jobs:`. Pour attendre plusieurs jobs : `needs: [test, lint]`.

!!Un job qui dépend d'un autre sans needs démarre immédiatement, même si les tests échouent!!

## Le moindre privilège du jeton

Chaque exécution reçoit un jeton `GITHUB_TOKEN` donnant accès au dépôt. Par défaut ses droits peuvent être larges. Déclarez au niveau du workflow `permissions: contents: read` : le jeton ne peut plus écrire dans le dépôt, et une action compromise y perd son principal levier.

Au niveau du workflow, `permissions` fixe le plancher pour tous les jobs. Si un seul job doit écrire (publier une release, par exemple), on lui ajoute son propre bloc `permissions:` sous son nom : il remplace celui du workflow pour ce job uniquement.

```yaml
permissions:
  contents: read          # tous les jobs : lecture seule
jobs:
  release:
    permissions:
      contents: write     # ce job seulement : il publie une release
```

!!Réduisez toujours les permissions du jeton, puis ajoutez seulement le droit dont un job a besoin!!

!!Un cache n'est jamais une source de vérité : en cas de doute, supprimez-le et relancez!!

## Borner le temps et éviter les doublons

`timeout-minutes: 10` arrête un job bloqué avant qu'il ne consomme des minutes facturées. Il se met dans **chaque** job, à côté de `runs-on` : un job sans limite peut tourner six heures.

`concurrency` avec `cancel-in-progress: true` annule l'exécution précédente d'une même branche quand un nouveau commit arrive : inutile de finir un test déjà périmé. Le `group` est une étiquette : deux runs qui ont la même étiquette ne tournent pas en même temps. Avec `ci-${{ github.ref }}`, l'étiquette contient le nom de la branche, donc chaque branche a sa propre file.

## Pas à pas : accélérer et protéger un workflow

1. Ouvrez `.github/workflows/ci.yml`.
2. Entre `on:` et `jobs:`, au niveau 0, ajoutez `permissions:` puis `contents: read` (2 espaces).
3. Juste dessous, au niveau 0, ajoutez `concurrency:` avec `group:` et `cancel-in-progress: true`.
4. Dans le job `test`, sous `runs-on`, ajoutez `timeout-minutes: 10` puis le bloc `strategy:` / `matrix:` / `python-version: ["3.11", "3.12"]`.
5. Dans l'étape setup-python, remplacez la version fixe par `${{ matrix.python-version }}` et ajoutez `cache: pip` dans le même `with:`.
6. Sous le job `test`, au niveau 1 (2 espaces), créez le job `build:` avec `needs: test`, `runs-on`, `timeout-minutes` et ses étapes.
7. Vérifiez : `actionlint` ne doit rien signaler, et l'onglet Actions doit montrer deux jobs `test (3.11)` et `test (3.12)`, puis `build`.

**À retenir :** `cache: pip` dans le `with:` de setup-python, matrice au niveau du job, `needs` dans le job qui attend, `permissions: contents: read` au niveau du workflow, `timeout-minutes` sur chaque job, `concurrency`.
