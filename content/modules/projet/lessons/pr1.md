# Projet fil rouge : l'application et sa CI

Jusqu'ici, chaque module avait ses propres exercices. Ce projet les **assemble** dans un seul dépôt, comme en entreprise : une petite API de commandes, testée par la CI, empaquetée en image, déployée sur Kubernetes, sur une infrastructure Terraform configurée par Ansible. À la fin, vous aurez un dépôt GitHub à montrer en entretien.

## Le plan du projet

| Étape | Ce que vous livrez | Module réutilisé |
|---|---|---|
| 1 | tests et CI | CI/CD |
| 2 | image durcie publiée sur ghcr.io | Docker, CI/CD |
| 3 | Deployment, Service, Kustomize | Kubernetes |
| 4 | infrastructure et state distant | Terraform |
| 5 | configuration des serveurs, README | Ansible |

Chaque étape **revérifie les précédentes** : si l'étape 4 casse la CI de l'étape 1, le contrôle le dit.

## L'application

`app/main.py` n'utilise que la bibliothèque standard : un serveur HTTP sur le port 8000, `GET /healthz` pour la santé et `POST /total` pour calculer une commande. `app/test_main.py` teste la fonction `total`.

```bash
pip install -r requirements.txt
python3 -m pytest -q app
python3 -m app.main &
curl -s http://127.0.0.1:8000/healthz
curl -s -X POST http://127.0.0.1:8000/total -d '[{"price": 2.5, "qty": 2}]'
```

!!Une application sans route de santé ne peut être surveillée ni par Docker, ni par Kubernetes, ni par un répartiteur!!

## La CI de départ

Le workflow minimal mais sûr :

- `on: push` vers `main` **et** `pull_request` : on teste avant et après la fusion ;
- `permissions: contents: read` : le jeton ne peut rien écrire ;
- un job `test` borné par `timeout-minutes` ;
- `setup-python` avec une version entre guillemets, puis `pip install` et `pytest`.

!!Une CI qu'on n'a jamais vue rouge n'a rien prouvé : cassez un test dans une pull request pour la voir bloquer!!

## Le workflow commenté

Ce fichier réutilise tout le module CI/CD. Chaque commentaire rappelle pourquoi la ligne est là, et où elle se place.

```yaml
# Fichier : .github/workflows/ci.yml (à la racine du dépôt commandes)
name: CI
on:
  push:
    branches: [main]            # après fusion : on revérifie main
  pull_request:                 # avant fusion : la PR est bloquée si rouge
permissions:                    # niveau 0 : vaut pour tous les jobs, y compris ceux des étapes suivantes
  contents: read
concurrency:                    # niveau 0 : un nouveau commit annule le run périmé
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:                         # le job que l'étape 2 attendra avec needs: [test]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"     # guillemets : une version est un texte
          cache: pip
      - run: pip install -r requirements.txt
      - run: pytest -q               # trouve app/test_main.py tout seul
```

L'arborescence du dépôt après cette étape :

```
commandes/
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── test_main.py
└── requirements.txt
```

## Pas à pas : l'étape 1

1. Dans le dossier du TP, lancez les tests en local : `pip install -r requirements.txt && python3 -m pytest -q app`. Ils doivent passer avant toute CI.
2. Créez `.github/workflows/ci.yml` avec le contenu ci-dessus. Écrivez-le vous-même plutôt que de le copier : c'est là que les niveaux d'indentation s'apprennent.
3. Validez : `actionlint .github/workflows/ci.yml`.
4. Créez le dépôt GitHub `commandes`, puis faites le premier commit et le premier push.
5. Ouvrez l'onglet **Actions** : le run doit être vert.
6. Créez une branche, cassez un test (changez un résultat attendu), poussez et ouvrez une pull request : la CI doit devenir rouge. Fermez ensuite la PR.

## Le dépôt vitrine

Créez le dépôt sur GitHub dès cette étape : l'historique compte. Des commits courts et nommés (`feat: api et ci`, `fix: arrondi du total`) racontent votre façon de travailler. Protégez `main` : pull request obligatoire et CI verte requise (Settings, Branches).

!!Ne poussez jamais un fichier .env ou une clé, même « pour tester » : l'historique Git garde tout!!

## Labo réel

```bash
git init -b main && git add . && git commit -m "feat: api et ci"
gh repo create commandes --public --source . --push
gh run watch
```

**À retenir :** un seul dépôt pour tout le projet ; une route `/healthz` ; une CI sur `push` et `pull_request`, en lecture seule, bornée ; la voir rouge au moins une fois ; protéger `main`.
