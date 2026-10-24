# Cache, matrice et dépendances entre jobs

Un pipeline lent est un pipeline que l'on contourne. Trois mécanismes le gardent rapide sans rien sacrifier : le cache, la matrice et l'enchaînement des jobs.

## Le cache des dépendances

Sans **cache**, chaque exécution retélécharge toutes les dépendances. Avec `actions/setup-python`, une ligne suffit : `cache: pip` mémorise le dossier de pip, clé calculée à partir de `requirements.txt`. Le cache est invalidé quand ce fichier change.

## La matrice

Pour tester sur plusieurs versions, ne copiez pas le job : déclarez une **matrice**. GitHub crée un **job** par valeur, en **parallèle**.

```yaml
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
```

## Enchaîner les jobs

Les jobs d'un workflow tournent en parallèle par défaut. `needs: test` fait attendre un job jusqu'à la réussite du job `test` : on ne construit ou ne déploie pas ce qui n'a pas passé les tests.

!!Un job qui dépend d'un autre sans needs démarre immédiatement, même si les tests échouent!!

## Le moindre privilège du jeton

Chaque exécution reçoit un jeton `GITHUB_TOKEN` donnant accès au dépôt. Par défaut ses droits peuvent être larges. Déclarez au niveau du workflow `permissions: contents: read` : le jeton ne peut plus écrire dans le dépôt, et une action compromise y perd son principal levier.

!!Réduisez toujours les permissions du jeton, puis ajoutez seulement le droit dont un job a besoin!!

!!Un cache n'est jamais une source de vérité : en cas de doute, supprimez-le et relancez!!

## Borner le temps et éviter les doublons

`timeout-minutes: 10` arrête un job bloqué avant qu'il ne consomme des minutes facturées. `concurrency` avec `cancel-in-progress: true` annule l'exécution précédente d'une même branche quand un nouveau commit arrive : inutile de finir un test déjà périmé.

**À retenir :** `cache: pip`, matrice, `needs`, `permissions: contents: read`, `timeout-minutes`, `concurrency`.
