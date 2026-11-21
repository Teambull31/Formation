# Environnements et déploiement continu

L'intégration continue vérifie le code. Le **déploiement continu** l'emmène plus loin : chaque commit fusionné sur `main` part automatiquement en préproduction, puis en production après une validation. Le pipeline devient le seul chemin vers la production.

## Livraison ou déploiement continu

- Livraison continue : chaque version est prête à partir, un humain appuie sur le bouton.
- Déploiement continu : la version part toute seule si tous les contrôles passent.

Dans les deux cas, on déploie **le même artefact** sur chaque environnement. On ne reconstruit pas entre la préproduction et la production : ce qui a été testé est ce qui part.

## Les déclencheurs d'un déploiement

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]
```

`push` filtré sur `main` déploie après chaque fusion. `workflow_dispatch` ajoute un bouton « Run workflow » dans l'onglet Actions, utile pour redéployer ou revenir en arrière.

!!Un workflow de déploiement déclenché sur pull_request exécuterait du code non relu avec les accès de la production!!

## Passer une valeur d'un job à l'autre

Chaque job tourne sur une machine différente : une variable du shell ne survit pas. On déclare des **outputs** de job, alimentés par un output d'étape.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.meta.outputs.version }}
    steps:
      - id: meta
        run: echo "version=1.0.${GITHUB_RUN_NUMBER}" >> "$GITHUB_OUTPUT"
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - env:
          VERSION: ${{ needs.build.outputs.version }}
        run: ./deploy.sh "$VERSION"
```

L'étape écrit `nom=valeur` dans le fichier `$GITHUB_OUTPUT`. L'ancienne commande `::set-output` est désactivée : ne la copiez pas depuis un vieux tutoriel.

## Les environnements GitHub

`environment: production` rattache le job à un **environnement** déclaré dans Settings > Environments. On y règle :

- des **réviseurs obligatoires** : le job attend qu'une personne approuve ;
- une restriction de branches : seul `main` peut déployer en production ;
- des secrets propres à l'environnement : le jeton de production n'est lisible que par les jobs de production.

```yaml
  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://app.example.test
```

!!Mettez les secrets de production dans l'environnement production, pas dans les secrets du dépôt : sinon n'importe quel workflow peut les lire!!

## Ne jamais interrompre un déploiement

En CI, `cancel-in-progress: true` économise des minutes. Pour un déploiement, c'est l'inverse : couper un job au milieu d'une migration laisse la production dans un état inconnu. On sérialise sans annuler :

```yaml
    concurrency:
      group: deploy-production
      cancel-in-progress: false
```

Deux fusions rapprochées partent alors l'une après l'autre.

!!cancel-in-progress: true sur un job de déploiement peut couper une migration de base de données en plein milieu!!

## Stratégies de mise en production

- **Rolling** : on remplace les instances une par une (le défaut de Kubernetes).
- **Blue/green** : on monte la nouvelle version à côté, on bascule le trafic d'un coup, l'ancienne reste prête pour un retour arrière.
- **Canary** : on envoie d'abord 5 % du trafic à la nouvelle version, on observe, puis on élargit.

Quelle que soit la stratégie, prévoyez le retour arrière **avant** le déploiement : redéployer la version précédente doit être un clic, pas une soirée.

## Pratique en plus

- Dessinez sur papier la chaîne build, staging, production : quelles données passent d'un job à l'autre ?
- Dans le TP, lancez `grep -n needs .github/workflows/deploy.yml` pour relire l'ordre des jobs.
- Sur un vrai dépôt, créez l'environnement `production` avec vous comme réviseur et regardez le job attendre votre approbation.

**À retenir :** même artefact partout, `push` sur `main` plus `workflow_dispatch`, outputs via `$GITHUB_OUTPUT` et `needs.<job>.outputs`, `environment:` pour l'approbation et les secrets, condition sur `github.ref`, déploiements sérialisés sans annulation, retour arrière prévu.
