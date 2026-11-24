# Workflows réutilisables et actions composites

Quand dix dépôts copient le même bloc de quinze lignes, une correction de sécurité doit être faite dix fois, et on en oublie toujours une. GitHub Actions offre deux outils pour écrire une fois et réutiliser partout.

## Deux niveaux de réutilisation

Une **action composite** regroupe des étapes. On l'appelle comme n'importe quelle action, à l'intérieur d'un job : `uses: ./.github/actions/setup`. Elle ne choisit pas la machine et ne peut pas porter de `needs` ni d'`environment`.

Un **workflow réutilisable** regroupe des jobs complets. Il se déclare avec `on: workflow_call` et s'appelle à la place des étapes d'un job : `jobs.test.uses: ./.github/workflows/reusable-test.yml`. Il choisit son runner, peut avoir plusieurs jobs, et reçoit des entrées typées.

Règle pratique : quelques étapes qui reviennent, une action composite. Un pipeline entier partagé entre équipes, un workflow réutilisable.

## L'arborescence à obtenir

Trois fichiers, trois rôles. Les chemins sont imposés par GitHub : un fichier mal placé n'est pas trouvé.

```
.github/
├── actions/
│   └── setup/
│       └── action.yml          ← action composite : le nom action.yml est obligatoire
└── workflows/
    ├── ci.yml                  ← l'appelant : déclenché par push et pull_request
    └── reusable-test.yml       ← le workflow réutilisable : déclenché par workflow_call
```

La chaîne d'appel se lit de haut en bas : `ci.yml` appelle `reusable-test.yml`, qui appelle l'action `setup`.

## Écrire l'action composite

Le fichier s'appelle obligatoirement `action.yml`, dans son propre dossier. Sa structure n'est **pas** celle d'un workflow : pas de `on:` ni de `jobs:`, mais `inputs:` et `runs:`.

```yaml
# Fichier : .github/actions/setup/action.yml
name: Préparer Python            # niveau 0 : nom de l'action
inputs:                          # niveau 0 : ce que l'appelant doit fournir
  python-version:                # niveau 1 : nom de l'entrée, choisi par vous
    required: true               # niveau 2 : propriété de cette entrée
runs:                            # niveau 0 : comment l'action s'exécute
  using: composite               # niveau 1 : « composite » = une suite d'étapes
  steps:                         # niveau 1 : à côté de using, PAS sous lui
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}   # lit l'entrée déclarée en haut
        cache: pip
    - run: pip install -r requirements.txt
      shell: bash                # ← obligatoire dans une action composite, aligné sur run
```

Pourquoi `steps` est-il au niveau de `using` ? Parce que les deux sont des propriétés de `runs`. Si `steps` est indenté sous `using`, YAML tente de donner des enfants à la valeur `composite`, et le fichier est invalide.

!!Dans une action composite, chaque étape run doit déclarer son shell : sans shell: bash, l'action est invalide!!

## Écrire un workflow réutilisable

```yaml
# Fichier : .github/workflows/reusable-test.yml
name: Tests réutilisables
on:
  workflow_call:                 # ← seul déclencheur : ce fichier n'est lancé que par un autre
    inputs:                      # enfant de workflow_call : les entrées sont propres à ce déclencheur
      python-version:
        type: string             # typé : l'appelant qui passe un mauvais type est refusé
        required: true
jobs:
  test:
    runs-on: ubuntu-latest       # ← le workflow réutilisable choisit SA machine
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4          # ← AVANT l'action locale : il apporte ses fichiers
      - uses: ./.github/actions/setup      # chemin relatif à la racine du dépôt
        with:
          python-version: ${{ inputs.python-version }}   # on relaie l'entrée à l'action
      - run: pytest -q
```

Les entrées se lisent avec `inputs.<nom>`. Elles sont typées (`string`, `number`, `boolean`) : une faute de frappe dans l'appelant est refusée avant le démarrage.

Remarquez que `inputs:` est **sous** `workflow_call:`, avec 4 espaces. Placé au niveau 0, il ne serait rattaché à aucun déclencheur et GitHub l'ignorerait.

## L'appeler

```yaml
# Fichier : .github/workflows/ci.yml
name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    strategy:                                  # la matrice reste dans l'appelant
      matrix:
        python-version: ["3.11", "3.12"]
    uses: ./.github/workflows/reusable-test.yml   # ← à la place de runs-on ET steps
    with:                                         # ← niveau du job, aligné sur uses
      python-version: ${{ matrix.python-version }}
```

Un job qui appelle un workflow n'a **ni `runs-on` ni `steps`** : tout vient du workflow appelé. Il peut en revanche avoir une matrice, `needs`, `if`, `permissions`.

Attention au niveau de `with:`. Dans une étape, `with:` est sous le tiret. Ici, il n'y a pas d'étape : `uses:` et `with:` sont des propriétés du **job**, alignées sur `strategy:`, à 4 espaces.

!!Un job appelant ne peut pas mélanger uses et steps : GitHub refuse le fichier entier!!

## Le piège du checkout

Une action locale (`./.github/actions/...`) est lue dans les fichiers du runner. Tant que `actions/checkout` n'a pas tourné, le dossier n'existe pas : l'étape échoue avec « Can't find action.yml ». Le checkout reste donc la première étape, **avant** toute action locale.

## Secrets et permissions

Un workflow appelé ne voit pas les secrets de l'appelant. On les passe un par un ou en bloc avec `secrets: inherit`. Préférez la liste explicite : on sait ce que reçoit chaque workflow.

```yaml
jobs:
  deploy:
    uses: ./.github/workflows/reusable-deploy.yml
    secrets:                                       # niveau du job, comme with
      DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}    # un secret nommé, et un seul
```

Côté workflow appelé, le secret se déclare sous `workflow_call:`, à côté de `inputs:` :

```yaml
on:
  workflow_call:
    inputs: {}
    secrets:
      DEPLOY_TOKEN:
        required: true
```

!!secrets: inherit transmet tous les secrets du dépôt, y compris ceux dont le workflow n'a pas besoin : réservez-le aux workflows de votre propre organisation!!

Les permissions du jeton suivent la même logique : l'appelant fixe le plafond, le workflow appelé ne peut que réduire.

## Partager entre dépôts

Depuis un autre dépôt, on référence `organisation/depot/.github/workflows/test.yml@v1`. Comme pour une action tierce, on épingle une version (un tag pour vos propres dépôts, un SHA complet pour ceux d'autrui).

## Pas à pas : factoriser un job dupliqué

1. Créez le dossier `.github/actions/setup/` et, dedans, `action.yml` : `name`, `inputs.python-version.required: true`, puis `runs:` avec `using: composite` et `steps:` au même niveau.
2. Dans ses étapes : `actions/setup-python@v5` avec `cache: pip`, puis `run: pip install -r requirements.txt` suivi de `shell: bash` aligné sur `run`.
3. Créez `.github/workflows/reusable-test.yml` avec `on: workflow_call:` et, dessous, l'entrée `python-version` (`type: string`, `required: true`).
4. Ajoutez le job `test` : `runs-on`, `timeout-minutes`, puis les étapes checkout, `./.github/actions/setup` (avec `python-version: ${{ inputs.python-version }}`) et `pytest -q`.
5. Dans `ci.yml`, supprimez les deux jobs dupliqués. Écrivez un seul job `test` avec la matrice, `uses: ./.github/workflows/reusable-test.yml` et `with:` au niveau du job.
6. Vérifiez l'arborescence avec `find .github -type f`, puis la syntaxe avec `actionlint`.

**À retenir :** action composite pour des étapes, `workflow_call` pour des jobs, entrées typées lues par `inputs.`, pas de `runs-on` dans un job appelant, `shell: bash` dans chaque étape composite, checkout avant toute action locale, secrets passés explicitement.
