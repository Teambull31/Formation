# Environnements et déploiement continu

L'intégration continue vérifie le code. Le **déploiement continu** l'emmène plus loin : chaque commit fusionné sur `main` part automatiquement en préproduction, puis en production après une validation. Le pipeline devient le seul chemin vers la production.

## Livraison ou déploiement continu

- Livraison continue : chaque version est prête à partir, un humain appuie sur le bouton.
- Déploiement continu : la version part toute seule si tous les contrôles passent.

Dans les deux cas, on déploie **le même artefact** sur chaque environnement. On ne reconstruit pas entre la préproduction et la production : ce qui a été testé est ce qui part.

## Le pipeline complet

Voici le fichier d'arrivée. La chaîne est `build`, puis `deploy-staging`, puis `deploy-production`. Chaque section de la leçon reprend un bloc.

```yaml
# Fichier : .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]               # ← seulement après une fusion sur main
  workflow_dispatch:               # ← bouton « Run workflow » pour relancer à la main
permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:                       # ← niveau du job : ce que build publie pour les autres
      version: ${{ steps.meta.outputs.version }}   # lit l'output de l'étape « meta »
    steps:
      - uses: actions/checkout@v4
      - id: meta                   # ← l'id permet de relire l'étape plus haut
        run: echo "version=1.0.${GITHUB_RUN_NUMBER}" >> "$GITHUB_OUTPUT"

  deploy-staging:
    needs: build                   # ← attend build ET donne accès à ses outputs
    runs-on: ubuntu-latest
    environment: staging           # ← niveau du job : rattache aux réglages « staging »
    steps:
      - env:
          VERSION: ${{ needs.build.outputs.version }}
        run: ./deploy.sh staging "$VERSION"

  deploy-production:
    needs: [build, deploy-staging] # ← build pour la version, staging pour l'ordre
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://app.example.test
    concurrency:                   # ← niveau du job : file d'attente de la production
      group: deploy-production
      cancel-in-progress: false    # ← on n'interrompt JAMAIS un déploiement
    steps:
      - env:
          VERSION: ${{ needs.build.outputs.version }}
        run: ./deploy.sh production "$VERSION"
```

## Les déclencheurs d'un déploiement

`push` filtré sur `main` déploie après chaque fusion. `workflow_dispatch` ajoute un bouton « Run workflow » dans l'onglet Actions, utile pour redéployer ou revenir en arrière.

`workflow_dispatch` peut proposer un choix à la personne qui clique. Les entrées se placent **sous** `workflow_dispatch:`, car elles n'existent que pour ce déclencheur :

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:                        # 4 espaces : enfant de workflow_dispatch
      environment:
        type: choice
        options: [staging, production]
```

!!Un workflow de déploiement déclenché sur pull_request exécuterait du code non relu avec les accès de la production!!

## Passer une valeur d'un job à l'autre

Chaque job tourne sur une machine différente : une variable du shell ne survit pas. On déclare des **outputs** de job, alimentés par un output d'étape.

Le chemin d'une valeur traverse trois endroits. Suivez `version` :

1. L'étape `meta` écrit `version=1.0.42` dans le fichier `$GITHUB_OUTPUT`. C'est un **output d'étape**, lisible par `steps.meta.outputs.version`.
2. Le job `build` le republie dans son bloc `outputs:`, au niveau du job, à côté de `runs-on`. C'est un **output de job**.
3. Le job `deploy-staging`, qui a `needs: build`, le lit par `needs.build.outputs.version`.

Sans l'étape 2, le job suivant ne voit rien : un output d'étape reste dans son job.

L'ancienne commande `::set-output` est désactivée : ne la copiez pas depuis un vieux tutoriel.

## Les environnements GitHub

`environment: production` rattache le job à un **environnement** déclaré dans Settings > Environments. On y règle :

- des **réviseurs obligatoires** : le job attend qu'une personne approuve ;
- une restriction de branches : seul `main` peut déployer en production ;
- des secrets propres à l'environnement : le jeton de production n'est lisible que par les jobs de production.

`environment:` accepte deux formes. La courte (`environment: staging`) donne seulement le nom. La longue est un bloc avec `name:` et `url:` ; l'URL s'affiche sur la page du run, comme lien vers l'application déployée.

!!Mettez les secrets de production dans l'environnement production, pas dans les secrets du dépôt : sinon n'importe quel workflow peut les lire!!

## La condition if

`if: github.ref == 'refs/heads/main'` se place au niveau du job, à côté de `needs`. Si la condition est fausse, le job est marqué « skipped » sans démarrer de machine. Avec `workflow_dispatch`, quelqu'un pourrait lancer le workflow depuis une autre branche : cette ligne l'empêche d'atteindre la production.

## Ne jamais interrompre un déploiement

En CI, `cancel-in-progress: true` économise des minutes. Pour un déploiement, c'est l'inverse : couper un job au milieu d'une migration laisse la production dans un état inconnu. On sérialise sans annuler. Deux fusions rapprochées partent alors l'une après l'autre.

!!cancel-in-progress: true sur un job de déploiement peut couper une migration de base de données en plein milieu!!

## Stratégies de mise en production

- **Rolling** : on remplace les instances une par une (le défaut de Kubernetes).
- **Blue/green** : on monte la nouvelle version à côté, on bascule le trafic d'un coup, l'ancienne reste prête pour un retour arrière.
- **Canary** : on envoie d'abord 5 % du trafic à la nouvelle version, on observe, puis on élargit.

Quelle que soit la stratégie, prévoyez le retour arrière **avant** le déploiement : redéployer la version précédente doit être un clic, pas une soirée.

## Pas à pas : construire le pipeline de déploiement

1. Sous `on:`, gardez seulement `push` avec `branches: [main]`, et ajoutez `workflow_dispatch:`. Supprimez `pull_request`.
2. Dans le job `build`, donnez `id: meta` à l'étape qui calcule la version, et faites-lui écrire `version=...` dans `"$GITHUB_OUTPUT"`.
3. Toujours dans `build`, au niveau du job, ajoutez `outputs:` avec `version: ${{ steps.meta.outputs.version }}`.
4. Dans `deploy-staging` : `needs: build`, `environment: staging`, et une étape avec `env: VERSION: ${{ needs.build.outputs.version }}`.
5. Dans `deploy-production` : `needs: [build, deploy-staging]`, la condition `if:`, l'environnement `production` et la même lecture de version.
6. Ajoutez le bloc `concurrency:` au job de production, avec `cancel-in-progress: false`.
7. Relisez l'ordre avec `grep -n needs .github/workflows/deploy.yml`, puis validez avec `actionlint`.

**À retenir :** même artefact partout, `push` sur `main` plus `workflow_dispatch`, outputs via `$GITHUB_OUTPUT` et `needs.<job>.outputs`, `environment:` pour l'approbation et les secrets, condition sur `github.ref`, déploiements sérialisés sans annulation, retour arrière prévu.
