# Votre premier workflow GitHub Actions

L'intégration continue (CI) lance automatiquement, à chaque modification, les contrôles que l'on oublierait de faire à la main : installer, tester, vérifier. Un test qui échoue est vu avant la fusion, pas chez le client.

## Workflow, job, étape

Un **workflow** est un fichier YAML dans `.github/workflows/`. Il contient des **jobs**, chacun s'exécute sur une machine neuve (le *runner*), et chaque job est une suite d'**étapes**. Une étape appelle soit une action réutilisable (`uses:`), soit une commande (`run:`).

Ces trois mots forment une hiérarchie, et le YAML la dessine avec l'indentation :

```
workflow (le fichier)
└── jobs
    └── test            ← un job, nommé librement
        ├── runs-on     ← sur quelle machine
        └── steps       ← la liste ordonnée des étapes
            ├── étape 1 (uses: checkout)
            ├── étape 2 (uses: setup-python)
            ├── étape 3 (run: pip install)
            └── étape 4 (run: pytest)
```

## Le fichier complet, ligne par ligne

Voici le workflow minimal. Chaque commentaire dit **pourquoi** la ligne est à cet endroit.

```yaml
# Fichier : .github/workflows/ci.yml   ← GitHub ne lit que ce dossier
name: CI                      # niveau 0 : nom affiché dans l'onglet Actions
on:                           # niveau 0 : QUAND le workflow démarre
  push:                       # niveau 1 (2 espaces) : un événement, enfant de on
  pull_request:               # niveau 1 : second événement, même niveau que push
jobs:                         # niveau 0 : QUOI faire ; contient tous les jobs
  test:                       # niveau 1 : nom du job, choisi par vous
    runs-on: ubuntu-latest    # niveau 2 : propriété du job test
    steps:                    # niveau 2 : propriété du job test, une liste
      - uses: actions/checkout@v4        # niveau 3 : « - » = un élément de la liste
      - uses: actions/setup-python@v5    # 2e élément : exécuté après le 1er
        with:                            # enfant de CETTE étape : ses paramètres
          python-version: "3.12"         # guillemets : sinon 3.10 deviendrait 3.1
      - run: pip install -r requirements.txt   # commande shell
      - run: pytest -q                         # dernière étape : les tests
```

Trois règles de structure à retenir :

- `name`, `on` et `jobs` sont au **niveau 0**, collés à gauche : ce sont les trois rubriques du fichier.
- Tout ce qui appartient à un job (`runs-on`, `steps`) est indenté **sous** le nom du job. Si `steps:` remonte au niveau de `test:`, YAML croit que `steps` est un second job.
- Chaque étape commence par un tiret `- `. Ce qui suit l'étape (`with:`) s'aligne sur le texte après le tiret, pas sur le tiret lui-même.

## Les déclencheurs

`on:` dit quand le workflow démarre. `push` réagit à chaque envoi de commits, `pull_request` à l'ouverture et à la mise à jour d'une demande de fusion. Avec les deux, la CI tourne sur vos branches et avant la fusion.

On peut restreindre un déclencheur. La branche filtrée se place **sous** l'événement concerné, car le filtre est une propriété de cet événement :

```yaml
on:
  push:
    branches: [main]      # niveau 2 : seulement les push sur main
  pull_request:           # toutes les demandes de fusion, sans filtre
```

!!Sans déclencheur pull_request, une demande de fusion peut être acceptée sans que personne n'ait vu les tests tourner!!

## Le runner est vide

Une machine neuve ne contient pas votre code. `actions/checkout` le récupère : c'est presque toujours la première étape. Ensuite `actions/setup-python` installe la version de Python voulue, puis vos commandes installent les dépendances et lancent les tests.

L'**ordre** des étapes est l'ordre d'exécution. Il suit une logique de dépendance :

1. `checkout` : sans le code, les fichiers `requirements.txt` et les tests n'existent pas.
2. `setup-python` : sans Python, `pip` n'existe pas.
3. `pip install` : sans dépendances, `pytest` échoue à l'import.
4. `pytest` : enfin, les tests.

!!Épinglez toujours une version d'action (actions/checkout@v4) : sans elle, vous ne savez pas quel code s'exécute!!

## Erreur d'indentation fréquente

YAML n'accepte que des **espaces**, jamais de tabulation, et 2 espaces par niveau est la convention. Une erreur fréquente : `with:` aligné sur le tiret.

```yaml
# FAUX : with est au niveau du tiret, YAML le rattache à la liste, pas à l'étape
      - uses: actions/setup-python@v5
      with:
        python-version: "3.12"

# JUSTE : with est aligné sur « uses », il appartient à la même étape
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
```

## Une étape plus lisible avec name

Une étape peut porter un `name:` qui apparaît dans le journal. Le `name` et le `run` sont deux clés de la **même** étape : un seul tiret, puis les deux clés alignées.

```yaml
      - name: Lancer les tests     # le tiret ouvre l'étape
        run: pytest -q             # aligné sur name : même étape
```

## Pas à pas : créer le workflow

1. À la racine du dépôt, créez le dossier `.github/workflows/` (le point au début compte).
2. Créez dedans le fichier `ci.yml`.
3. Écrivez les trois rubriques au niveau 0 : `name:`, `on:`, `jobs:`.
4. Sous `on:`, ajoutez `push:` et `pull_request:` avec 2 espaces.
5. Sous `jobs:`, nommez un job `test:` (2 espaces), puis sous lui `runs-on: ubuntu-latest` et `steps:` (4 espaces).
6. Ajoutez les étapes dans l'ordre checkout, setup-python, installation, tests, chacune commençant par `- ` (6 espaces avant le tiret).
7. Validez la syntaxe en local : `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` ou, mieux, `actionlint`.
8. Commitez et poussez : l'onglet **Actions** du dépôt affiche l'exécution.

## Lire un échec

Quand une étape échoue, le job s'arrête et la page du run affiche le journal de l'étape en erreur. Reproduisez la commande en local avant de modifier le workflow : la plupart des échecs de CI sont des échecs de test ordinaires.

Exemple : le journal montre `ModuleNotFoundError: No module named 'requests'` à l'étape `pytest`. La cause n'est pas pytest : la dépendance manque dans `requirements.txt`. Ajoutez-la, relancez `pip install -r requirements.txt && pytest -q` chez vous, puis poussez.

!!Ne désactivez pas un test qui échoue pour faire passer la CI : corrigez le code ou le test!!

**À retenir :** workflow, job, étape, runner vide, `checkout` en premier, déclencheurs `push` et `pull_request`, versions d'actions épinglées, 2 espaces par niveau.
