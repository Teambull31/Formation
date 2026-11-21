# Fiche de révision : CI/CD avec GitHub Actions

## Vocabulaire

- **Workflow** : fichier YAML dans `.github/workflows/`. Contient des jobs.
- **Job** : suite d'étapes sur un runner neuf. Les jobs tournent en parallèle sauf `needs:`.
- **Étape** : `uses:` (une action) ou `run:` (une commande shell).
- **Runner** : machine vide. Rien ne survit d'un job à l'autre.
- **Action** : brique réutilisable `propriétaire/nom@version`.

## Squelette à connaître par cœur

```yaml
name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -r requirements.txt
      - run: pytest -q
  build:
    needs: test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: python -m build
```

## Déclencheurs

- `push` / `pull_request` : la CI tourne sur les branches et avant la fusion.
- `push: branches: [main]` : déploiement après fusion.
- `push: tags: ["v*"]` : publication d'une release.
- `workflow_dispatch` : bouton manuel (redéployer, revenir en arrière).
- `schedule: - cron: "0 3 * * 1"` : tâche planifiée (UTC).
- `workflow_call` : workflow réutilisable.
- !!pull_request_target donne secrets et écriture à du code venu d'un fork : à proscrire!!

## Vitesse

- `cache: pip` (ou `npm`, `gradle`) dans `setup-*`, ou `actions/cache@v4` avec une clé sur le fichier de verrou.
- Matrice pour tester plusieurs versions en parallèle.
- `concurrency` + `cancel-in-progress: true` en CI : le nouveau run annule l'ancien.
- `timeout-minutes` sur chaque job : un job bloqué consomme 6 h par défaut.

## Passer des données

- Entre étapes : `echo "cle=valeur" >> "$GITHUB_OUTPUT"`, lu par `steps.<id>.outputs.cle`.
- Entre jobs : `outputs:` du job, lu par `needs.<job>.outputs.cle` (le job doit être dans `needs`).
- Fichiers entre jobs : `actions/upload-artifact@v4` puis `actions/download-artifact@v4`, même `name`, `retention-days` courte.
- Variable pour les étapes suivantes : `echo "NOM=valeur" >> "$GITHUB_ENV"`.

## Réutiliser

- Action composite : `.github/actions/<nom>/action.yml`, `runs: using: composite`, `shell: bash` sur chaque `run`.
- Workflow réutilisable : `on: workflow_call` avec `inputs:` typées ; l'appelant a `uses:` et `with:`, **ni `runs-on` ni `steps`**.
- Action locale : seulement **après** `actions/checkout`.
- Secrets vers un workflow appelé : liste explicite plutôt que `secrets: inherit`.

## Sécurité : la liste de contrôle

- `permissions: contents: read` au niveau du workflow, droits d'écriture au niveau du seul job qui en a besoin.
- Secrets dans Settings, lus via `${{ secrets.X }}` dans `env:` ou `with:`, jamais dans le texte d'un `run:`.
- !!Jamais ${{ github.event.* }} dans un run: : passez par env: puis "$VARIABLE" (injection de commande)!!
- Actions `actions/*` sur un tag de version ; actions tierces sur un **SHA de 40 caractères**.
- Secrets de production dans l'environnement `production`, pas au niveau du dépôt.
- Un secret commité est compromis : on le **révoque**, supprimer le commit ne suffit pas.

## Déploiement continu

- Même artefact sur tous les environnements : on ne reconstruit pas.
- `environment: production` : réviseurs obligatoires, branches autorisées, secrets dédiés.
- `if: github.ref == 'refs/heads/main'` sur le job de production.
- !!Concurrence de déploiement : cancel-in-progress: false, on ne coupe jamais un déploiement!!
- Stratégies : rolling, blue/green, canary. Le retour arrière se prévoit avant.

## OIDC et releases

- `id-token: write` sur le seul job qui se connecte au cloud, puis `role-to-assume` (AWS), `workload_identity_provider` (GCP) ou `azure/login` avec client-id.
- Aucune clé statique (`AWS_SECRET_ACCESS_KEY`) dans GitHub.
- La politique de confiance du rôle filtre le dépôt et la branche ou le tag.
- Release : `gh release create "$GITHUB_REF_NAME" dist/*` avec `GH_TOKEN: ${{ github.token }}` et `contents: write` sur ce job.
- SemVer : `MAJEUR.MINEUR.CORRECTIF` ; un tag publié ne se déplace jamais.

## Dépanner un run

- Lire le journal de la **première** étape rouge, pas de la dernière.
- Reproduire la commande en local avant de toucher au workflow.
- « Can't find action.yml » : action locale avant checkout.
- Valeur vide depuis un autre job : job absent de `needs`, ou output non déclaré.
- Workflow qui ne démarre pas : erreur YAML (indentation) ou filtre `branches`/`paths` trop strict.
- Ressource refusée (403) : permission manquante dans `permissions:`.
- Rejouer avec plus de détails : relancer le job avec « Enable debug logging ».

## Questions d'entretien

- CI, livraison continue, déploiement continu : quelles différences ?
- Pourquoi épingler une action tierce sur un SHA plutôt qu'un tag ?
- Comment éviter qu'une PR venue d'un fork lise vos secrets ?
- Comment passer une version calculée dans un job à un autre job ?
- Pourquoi OIDC plutôt qu'une clé d'accès cloud ?
