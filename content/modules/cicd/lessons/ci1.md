# Votre premier workflow GitHub Actions

L'intégration continue (CI) lance automatiquement, à chaque modification, les contrôles que l'on oublierait de faire à la main : installer, tester, vérifier. Un test qui échoue est vu avant la fusion, pas chez le client.

## Workflow, job, étape

Un **workflow** est un fichier YAML dans `.github/workflows/`. Il contient des **jobs**, chacun s'exécute sur une machine neuve (le *runner*), et chaque job est une suite d'**étapes**. Une étape appelle soit une action réutilisable (`uses:`), soit une commande (`run:`).

```yaml
name: CI
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest -q
```

## Les déclencheurs

`on:` dit quand le workflow démarre. `push` réagit à chaque envoi de commits, `pull_request` à l'ouverture et à la mise à jour d'une demande de fusion. Avec les deux, la CI tourne sur vos branches et avant la fusion.

!!Sans déclencheur pull_request, une demande de fusion peut être acceptée sans que personne n'ait vu les tests tourner!!

## Le runner est vide

Une machine neuve ne contient pas votre code. `actions/checkout` le récupère : c'est presque toujours la première étape. Ensuite `actions/setup-python` installe la version de Python voulue, puis vos commandes installent les dépendances et lancent les tests.

!!Épinglez toujours une version d'action (actions/checkout@v4) : sans elle, vous ne savez pas quel code s'exécute!!

## Lire un échec

Quand une étape échoue, le job s'arrête et la page du run affiche le journal de l'étape en erreur. Reproduisez la commande en local avant de modifier le workflow : la plupart des échecs de CI sont des échecs de test ordinaires.

!!Ne désactivez pas un test qui échoue pour faire passer la CI : corrigez le code ou le test!!

**À retenir :** workflow, job, étape, runner vide, `checkout` en premier, déclencheurs `push` et `pull_request`, versions d'actions épinglées.
