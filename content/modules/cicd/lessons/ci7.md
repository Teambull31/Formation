# Répare la panne : un pipeline rouge

Écrire un workflow est la moitié du métier. L'autre moitié, c'est le lundi matin où tout est rouge. Cette leçon donne une **méthode** de diagnostic, puis le TP vous met devant cinq pannes réelles à la fois.

## La méthode en quatre temps

1. **Constater** : quel job, quelle étape, quel commit, quel déclencheur ? L'onglet Actions répond en dix secondes.
2. **Lire la première erreur** de l'étape rouge, pas la dernière ligne : les suivantes sont souvent des conséquences.
3. **Classer** la panne dans une famille (tableau ci-dessous). La famille dit où regarder.
4. **Corriger une chose à la fois**, puis relancer. Deux corrections d'un coup cachent laquelle a marché.

!!Relancer un job rouge sans lire l'erreur, c'est espérer : une panne intermittente reviendra au pire moment!!

## Les familles de pannes

| Symptôme | Famille | Où regarder |
|---|---|---|
| Aucun run sur la PR | déclencheur | `on:`, `branches`, `paths`, emplacement du fichier |
| Version bizarre, booléen inattendu | YAML | guillemets autour des versions, `on`/`yes` |
| Dépendances périmées, cache jamais invalidé | cache | `key` et `hashFiles` sur le bon fichier |
| Déploiement malgré des tests rouges | dépendance | `needs:` entre jobs |
| `403 Resource not accessible by integration` | permissions | bloc `permissions:` du job |
| Secret vide sur une PR de fork | secret | les forks ne reçoivent pas les secrets |

## Chaque panne, avec sa correction en place

Pour chaque famille, voici le morceau fautif et sa correction, **à l'endroit exact** où elle se place dans le fichier.

### Déclencheur : la PR ne lance rien

```yaml
# FAUX : seulement les push sur master, branche renommée en main depuis
on:
  push:
    branches: [master]

# JUSTE : main, les PR, et les tags de version
on:
  push:
    branches: [main]
    tags: ["v*"]          # sous push, à côté de branches : un autre filtre du même événement
  pull_request:           # niveau 1 : un événement à part entière, aligné sur push
```

### YAML : la mauvaise version de Python

```yaml
# FAUX : YAML lit le nombre 3.10, qui vaut 3.1
          python-version: 3.10
# JUSTE : une chaîne de caractères, transmise telle quelle
          python-version: "3.10"
```

### Cache : la clé ne change jamais

```yaml
# FAUX : requirements.txt n'existe plus, hashFiles renvoie une chaîne vide
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}

# JUSTE : le fichier réel ; la clé change dès qu'une dépendance change
          key: pip-${{ runner.os }}-${{ hashFiles('requirements/base.txt') }}
```

### Dépendance : le déploiement n'attend pas les tests

```yaml
  deploy:
    needs: test           # ← ajouté au niveau du job deploy, à côté de runs-on
    runs-on: ubuntu-latest
```

### Permissions : 403 au moment de créer la release

```yaml
  release:
    needs: test
    runs-on: ubuntu-latest
    permissions:          # ← dans le job release seulement, pas au niveau 0
      contents: write
```

Mettre `contents: write` au niveau 0 corrigerait aussi l'erreur, mais donnerait l'écriture à tous les jobs : c'est la mauvaise correction.

## Les pièges classiques

- **YAML convertit tout seul** : `python-version: 3.10` devient le nombre 3.1. Toute version s'écrit entre guillemets.
- `hashFiles('requirements.txt')` sur un fichier absent renvoie une chaîne vide : la clé ne change jamais, le cache restauré est périmé.
- Sans `needs:`, les jobs tournent **en parallèle** : `deploy` n'attend pas `test`.
- Après un renommage `master` vers `main`, tout `branches: [master]` devient silencieux.

!!Une clé de cache qui ne change jamais est pire que pas de cache : la CI teste avec d'anciennes dépendances!!

## Obtenir plus d'informations

- **Re-run jobs** puis « Enable debug logging » : les actions affichent leurs commandes internes.
- Le secret `ACTIONS_STEP_DEBUG` à `true` active ce mode pour tous les runs ; retirez-le ensuite.
- Une étape `run: env | sort` montre les variables (jamais en présence de secrets).
- `act` rejoue un workflow en local dans Docker, pratique pour une boucle courte.

!!Ne collez jamais un journal de débogage dans un ticket public sans le relire : il peut contenir des URL internes ou des jetons!!

## Pas à pas : le TP du lundi rouge

1. Lisez les incidents dans l'ordre : `cat incidents/01-pull-request.txt`, puis les suivants. Notez pour chacun le symptôme exact.
2. Pour chaque symptôme, cherchez sa ligne dans le tableau des familles et écrivez la cause dans `diagnostic.yaml`, à la place du `?`.
3. Ouvrez `.github/workflows/ci.yml` et corrigez **une** panne. Relisez le bloc corrigé : bonne clé parente, bon nombre d'espaces.
4. Validez la syntaxe après chaque correction (`actionlint .github/workflows/ci.yml`), puis passez à la suivante.
5. Quand les cinq sont corrigées, lancez la vérification du TP.

## Après la correction

Une panne corrigée sans trace reviendra. Notez dans la PR la cause, la correction et la vérification. Si la panne était bête, ajoutez un garde-fou : `actionlint` en pré-commit attrape les erreurs YAML et les expressions invalides.

## Labo réel

```bash
actionlint .github/workflows/ci.yml   # binaire : https://github.com/rhysd/actionlint/releases
gh run list --limit 5
gh run view --log-failed
gh run rerun --failed --debug
```

**À retenir :** constater, lire la première erreur, classer, corriger une chose à la fois ; versions entre guillemets ; `hashFiles` sur un fichier qui existe ; `needs:` pour ordonner ; `permissions:` au plus près du job ; le mode débogage pour en voir plus.
