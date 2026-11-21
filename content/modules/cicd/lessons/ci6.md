# Artefacts, releases et OIDC vers le cloud

Dernière marche du pipeline : produire un livrable versionné, le publier, et se connecter au cloud **sans aucune clé stockée** dans GitHub.

## Les artefacts entre jobs

Les fichiers produits par un job disparaissent avec sa machine. Pour les transmettre, on les téléverse puis on les télécharge :

```yaml
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
          retention-days: 7
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
```

Le `name` doit être identique des deux côtés. `retention-days` limite la durée de stockage : un artefact oublié coûte de l'espace et peut contenir des données internes.

!!Un artefact est téléchargeable par toute personne qui lit le dépôt : n'y mettez jamais de fichier .env ni de clé!!

## Publier sur un tag

On publie une version quand on pousse un tag `v1.2.0` :

```yaml
on:
  push:
    tags: ["v*"]
```

Le nom du tag est dans la variable `GITHUB_REF_NAME`. La commande `gh` est installée sur les runners :

```yaml
      - env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" dist/*
```

Créer une release écrit dans le dépôt : ce job seul reçoit `contents: write`, au niveau du job. Le reste du workflow garde `contents: read`.

## Le problème des clés statiques

La méthode ancienne : créer une clé d'accès AWS (ou un compte de service GCP), la coller dans `secrets.AWS_SECRET_ACCESS_KEY`. Cette clé vit des mois, fonctionne depuis n'importe où, et fuit un jour dans un journal ou un fork.

!!Une clé d'accès cloud stockée dans les secrets GitHub est valable partout et longtemps : c'est la première chose qu'un attaquant cherche!!

## OIDC : des identifiants de quelques minutes

Avec **OIDC** (OpenID Connect), GitHub signe un jeton qui dit « je suis le workflow release.yml du dépôt X, sur le tag v1.2.0 ». Le cloud vérifie la signature et donne des droits temporaires, valables une heure au plus. Aucun secret n'est stocké.

```yaml
  publish:
    permissions:
      contents: write
      id-token: write
    steps:
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          role-to-assume: arn:aws:iam::123456789012:role/release
          aws-region: eu-west-3
```

Le SHA ci-dessus est un exemple : copiez celui du tag voulu depuis la page des releases de l'action. `id-token: write` autorise le job à demander ce jeton. Côté cloud, la **politique de confiance** du rôle restreint qui peut l'assumer : ce dépôt, cette branche ou ce tag. Sans cette restriction, n'importe quel dépôt GitHub pourrait assumer votre rôle.

!!Donnez id-token: write uniquement au job qui se connecte au cloud, jamais au niveau du workflow entier!!

## Versionner proprement

- **SemVer** : `MAJEUR.MINEUR.CORRECTIF`. Une rupture de compatibilité incrémente le majeur.
- Un tag publié ne se déplace pas : une correction donne `v1.2.1`, pas un `v1.2.0` réécrit.
- La release liste les changements : vos messages de commit (Conventional Commits : `feat:`, `fix:`) peuvent la générer.

## La chaîne d'approvisionnement

Pour aller plus loin, les projets sérieux signent leurs artefacts (Sigstore, `cosign`) et publient une **attestation de provenance** (`actions/attest-build-provenance`) : on peut prouver qu'un binaire vient bien de ce workflow et de ce commit.

## Pratique en plus

- Dans le TP, vérifiez que `name:` de l'upload et du download sont identiques avec `grep -n "name: dist" -r .github`.
- Cherchez toutes les permissions accordées : `grep -n -A3 permissions .github/workflows/release.yml`.
- Sur un vrai dépôt, poussez un tag `git tag v0.1.0 && git push origin v0.1.0` et regardez la release apparaître.

**À retenir :** upload et download d'artefacts avec le même nom et une rétention courte, release sur tag `v*` avec `GITHUB_REF_NAME`, `contents: write` sur le seul job qui publie, OIDC avec `id-token: write` au niveau du job, aucune clé cloud statique, actions tierces épinglées sur un SHA.
