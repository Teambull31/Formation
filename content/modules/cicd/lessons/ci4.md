# Workflows réutilisables et actions composites

Quand dix dépôts copient le même bloc de quinze lignes, une correction de sécurité doit être faite dix fois, et on en oublie toujours une. GitHub Actions offre deux outils pour écrire une fois et réutiliser partout.

## Deux niveaux de réutilisation

Une **action composite** regroupe des étapes. On l'appelle comme n'importe quelle action, à l'intérieur d'un job : `uses: ./.github/actions/setup`. Elle ne choisit pas la machine et ne peut pas porter de `needs` ni d'`environment`.

Un **workflow réutilisable** regroupe des jobs complets. Il se déclare avec `on: workflow_call` et s'appelle à la place des étapes d'un job : `jobs.test.uses: ./.github/workflows/reusable-test.yml`. Il choisit son runner, peut avoir plusieurs jobs, et reçoit des entrées typées.

Règle pratique : quelques étapes qui reviennent, une action composite. Un pipeline entier partagé entre équipes, un workflow réutilisable.

## Écrire un workflow réutilisable

```yaml
name: Tests réutilisables
on:
  workflow_call:
    inputs:
      python-version:
        type: string
        required: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest -q
```

Les entrées se lisent avec `inputs.<nom>`. Elles sont typées (`string`, `number`, `boolean`) : une faute de frappe dans l'appelant est refusée avant le démarrage.

## L'appeler

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    uses: ./.github/workflows/reusable-test.yml
    with:
      python-version: ${{ matrix.python-version }}
```

Un job qui appelle un workflow n'a **ni `runs-on` ni `steps`** : tout vient du workflow appelé. Il peut en revanche avoir une matrice, `needs`, `if`, `permissions`.

!!Un job appelant ne peut pas mélanger uses et steps : GitHub refuse le fichier entier!!

## Écrire une action composite

Le fichier s'appelle obligatoirement `action.yml`, dans son propre dossier.

```yaml
name: Préparer Python
inputs:
  python-version:
    required: true
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: pip
    - run: pip install -r requirements.txt
      shell: bash
```

!!Dans une action composite, chaque étape run doit déclarer son shell : sans shell: bash, l'action est invalide!!

## Le piège du checkout

Une action locale (`./.github/actions/...`) est lue dans les fichiers du runner. Tant que `actions/checkout` n'a pas tourné, le dossier n'existe pas : l'étape échoue avec « Can't find action.yml ». Le checkout reste donc la première étape, **avant** toute action locale.

## Secrets et permissions

Un workflow appelé ne voit pas les secrets de l'appelant. On les passe un par un (`secrets: DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}`) ou en bloc avec `secrets: inherit`. Préférez la liste explicite : on sait ce que reçoit chaque workflow.

!!secrets: inherit transmet tous les secrets du dépôt, y compris ceux dont le workflow n'a pas besoin : réservez-le aux workflows de votre propre organisation!!

Les permissions du jeton suivent la même logique : l'appelant fixe le plafond, le workflow appelé ne peut que réduire.

## Partager entre dépôts

Depuis un autre dépôt, on référence `organisation/depot/.github/workflows/test.yml@v1`. Comme pour une action tierce, on épingle une version (un tag pour vos propres dépôts, un SHA complet pour ceux d'autrui).

## Pratique en plus

- Dans le terminal du TP, lancez `find .github -type f` pour voir l'arborescence attendue.
- Comparez la taille de `ci.yml` avant et après : la duplication doit disparaître.
- Si vous avez un dépôt GitHub, poussez le résultat et ouvrez l'onglet Actions : le graphe affiche « test (3.11) / test » pour chaque appel.

**À retenir :** action composite pour des étapes, `workflow_call` pour des jobs, entrées typées lues par `inputs.`, pas de `runs-on` dans un job appelant, `shell: bash` dans chaque étape composite, checkout avant toute action locale, secrets passés explicitement.
