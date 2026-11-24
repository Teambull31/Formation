# Artefacts, releases et OIDC vers le cloud

Dernière marche du pipeline : produire un livrable versionné, le publier, et se connecter au cloud **sans aucune clé stockée** dans GitHub.

## Le workflow complet

Voici le fichier d'arrivée. Deux jobs : `build` fabrique le paquet, `publish` le récupère, se connecte au cloud et crée la release.

```yaml
# Fichier : .github/workflows/release.yml
name: Release
on:
  push:
    tags: ["v*"]                  # ← un tag v1.2.0 déclenche la publication
permissions:
  contents: read                  # ← plancher pour tous les jobs : lecture seule

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: pip install build && python -m build      # produit dist/*.whl et dist/*.tar.gz
      - uses: actions/upload-artifact@v4               # ← DERNIÈRE étape : après la production des fichiers
        with:
          name: dist                                   # ← l'étiquette, à réutiliser à l'identique
          path: dist/
          retention-days: 7

  publish:
    needs: build                  # ← l'artefact n'existe qu'après build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:                  # ← niveau du job : remplace le plancher pour CE job seulement
      contents: write             # créer la release écrit dans le dépôt
      id-token: write             # demander un jeton OIDC
    steps:
      - uses: actions/download-artifact@v4             # ← PREMIÈRE étape : on récupère avant d'utiliser
        with:
          name: dist                                   # même nom que l'upload
          path: dist/
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          role-to-assume: arn:aws:iam::123456789012:role/release
          aws-region: eu-west-3
      - run: aws s3 cp dist/ s3://releases-exemple/ --recursive
      - env:
          GH_TOKEN: ${{ github.token }}                # gh lit son jeton dans cette variable
        run: gh release create "$GITHUB_REF_NAME" dist/*
```

## Les artefacts entre jobs

Les fichiers produits par un job disparaissent avec sa machine. Pour les transmettre, on les téléverse puis on les télécharge.

L'ordre des étapes compte des deux côtés :

- dans `build`, l'upload vient **après** `python -m build` : avant, le dossier `dist/` est vide ;
- dans `publish`, le download vient **en premier** : les étapes suivantes ont besoin des fichiers.

Le `name` doit être identique des deux côtés. `retention-days` limite la durée de stockage : un artefact oublié coûte de l'espace et peut contenir des données internes.

!!Un artefact est téléchargeable par toute personne qui lit le dépôt : n'y mettez jamais de fichier .env ni de clé!!

## Publier sur un tag

On publie une version quand on pousse un tag `v1.2.0`. `tags:` est un filtre de l'événement `push`, il se place donc sous `push:`, comme `branches:`.

Le nom du tag est dans la variable `GITHUB_REF_NAME`. La commande `gh` est installée sur les runners et lit son jeton dans la variable `GH_TOKEN`. Le jeton passe par `env:`, à côté de `run:`, jamais dans le texte de la commande.

Créer une release écrit dans le dépôt : ce job seul reçoit `contents: write`, au niveau du job. Le reste du workflow garde `contents: read`.

## Le problème des clés statiques

La méthode ancienne : créer une clé d'accès AWS (ou un compte de service GCP), la coller dans `secrets.AWS_SECRET_ACCESS_KEY`. Cette clé vit des mois, fonctionne depuis n'importe où, et fuit un jour dans un journal ou un fork.

```yaml
# AVANT : clé statique, à supprimer
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}         # ✗ clé longue durée
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }} # ✗
          aws-region: eu-west-3

# APRÈS : OIDC, aucune clé stockée
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          role-to-assume: arn:aws:iam::123456789012:role/release      # ✓ un rôle, pas une clé
          aws-region: eu-west-3
```

!!Une clé d'accès cloud stockée dans les secrets GitHub est valable partout et longtemps : c'est la première chose qu'un attaquant cherche!!

## OIDC : des identifiants de quelques minutes

Avec **OIDC** (OpenID Connect), GitHub signe un jeton qui dit « je suis le workflow release.yml du dépôt X, sur le tag v1.2.0 ». Le cloud vérifie la signature et donne des droits temporaires, valables une heure au plus. Aucun secret n'est stocké.

Le SHA de l'action est un exemple : copiez celui du tag voulu depuis la page des releases de l'action. `id-token: write` autorise le job à demander ce jeton. Côté cloud, la **politique de confiance** du rôle restreint qui peut l'assumer : ce dépôt, cette branche ou ce tag. Sans cette restriction, n'importe quel dépôt GitHub pourrait assumer votre rôle.

Le bloc `permissions:` d'un job **remplace** celui du workflow, il ne s'y ajoute pas. C'est pourquoi `publish` répète les deux droits dont il a besoin, et seulement eux.

!!Donnez id-token: write uniquement au job qui se connecte au cloud, jamais au niveau du workflow entier!!

## Versionner proprement

- **SemVer** : `MAJEUR.MINEUR.CORRECTIF`. Une rupture de compatibilité incrémente le majeur.
- Un tag publié ne se déplace pas : une correction donne `v1.2.1`, pas un `v1.2.0` réécrit.
- La release liste les changements : vos messages de commit (Conventional Commits : `feat:`, `fix:`) peuvent la générer.

## La chaîne d'approvisionnement

Pour aller plus loin, les projets sérieux signent leurs artefacts (Sigstore, `cosign`) et publient une **attestation de provenance** (`actions/attest-build-provenance`) : on peut prouver qu'un binaire vient bien de ce workflow et de ce commit.

## Pas à pas : sécuriser la publication

1. Sous `on:`, remplacez le déclencheur par `push:` avec `tags: ["v*"]`.
2. Au niveau 0, remplacez `permissions: write-all` par `permissions:` / `contents: read`.
3. Dans `build`, ajoutez en dernière étape `actions/upload-artifact@v4` avec `name: dist`, `path: dist/` et `retention-days: 7`.
4. Dans `publish`, ajoutez `needs: build`, puis le bloc `permissions:` du job avec `contents: write` et `id-token: write`.
5. En première étape de `publish`, téléchargez l'artefact avec le même `name: dist`.
6. Dans l'étape `configure-aws-credentials`, supprimez les deux lignes de clés et ajoutez `role-to-assume:`. Vérifiez que l'action est épinglée sur un SHA de 40 caractères.
7. Ajoutez l'étape `gh release create "$GITHUB_REF_NAME" dist/*`, avec `GH_TOKEN` dans son `env:`.
8. Contrôlez : `grep -n "name: dist" -r .github` doit afficher deux lignes, et `grep -n -A3 permissions .github/workflows/release.yml` ne doit montrer aucun `write-all`.

**À retenir :** upload et download d'artefacts avec le même nom et une rétention courte, release sur tag `v*` avec `GITHUB_REF_NAME`, `contents: write` sur le seul job qui publie, OIDC avec `id-token: write` au niveau du job, aucune clé cloud statique, actions tierces épinglées sur un SHA.
