# Injections SQL et de commandes

L'injection est la plus ancienne famille de failles web et elle reste dans le haut du classement OWASP. Le principe est toujours le même : l'application construit du texte qui sera interprété (une requête, une commande) en y collant une donnée venue de l'extérieur.

## L'injection SQL

```python
query = "SELECT id, name FROM users WHERE name = '" + name + "'"
```

Avec `name = "' OR '1'='1"`, la requête devient `... WHERE name = '' OR '1'='1'` : elle renvoie tout le monde. Avec `x'; DROP TABLE users; --`, elle supprime la table. Le texte de l'utilisateur est devenu du **code SQL**.

## La parade : les paramètres liés

On sépare la requête de ses données. Le moteur reçoit la requête avec des emplacements `?`, puis les valeurs à part : il ne les interprète jamais comme du SQL.

```python
conn.execute("SELECT id, name FROM users WHERE name = ?", (name,))
```

!!Ne construisez jamais une requête SQL avec +, un f-string ou format() à partir d'une donnée externe!!

Remarquez que « O'Brien » est un nom valide : une défense qui retire ou double les apostrophes à la main casse les noms légitimes et se contourne. Le paramètre lié règle les deux problèmes.

## L'injection de commande

```python
subprocess.run("wc -l " + path, shell=True)
```

Avec `shell=True`, tout le texte est lu par un shell. Un chemin comme `data.txt; touch PWNED` exécute aussi la seconde commande. La parade ressemble à la précédente : on passe une **liste d'arguments**, sans shell.

```python
subprocess.run(["wc", "-l", "--", path], capture_output=True, text=True, check=True)
```

Chaque élément de la liste est un argument, jamais du code. Les espaces dans un nom de fichier ne posent plus de problème.

!!shell=True avec une donnée externe est une faille : préférez une liste d'arguments!!

## Les deux fonctions, avant et après

```python
# AVANT : app.py vulnérable
import sqlite3
import subprocess

def find_user(conn, name):
    query = "SELECT id, name FROM users WHERE name = '" + name + "'"   # ✗ la donnée devient du SQL
    return conn.execute(query).fetchall()

def count_lines(path):
    out = subprocess.run("wc -l " + path, shell=True,                  # ✗ la donnée devient du shell
                         capture_output=True, text=True)
    return int(out.stdout.split()[0])
```

```python
# APRÈS : app.py corrigé
import sqlite3
import subprocess

def find_user(conn, name):
    return conn.execute(
        "SELECT id, name FROM users WHERE name = ?",   # ← la requête, figée, avec un emplacement
        (name,),                                      # ← les valeurs, à part ; la virgule fait un tuple
    ).fetchall()

def count_lines(path):
    out = subprocess.run(
        ["wc", "-l", "--", path],    # ← une liste : programme, options, fin des options, fichier
        capture_output=True,         # récupère la sortie au lieu de l'afficher
        text=True,                   # en texte, pas en octets
        check=True,                  # lève une exception si wc échoue
    )                                # pas de shell=True : aucun shell ne lit le chemin
    return int(out.stdout.split()[0])
```

Trois détails qui font la différence :

- `(name,)` avec la virgule : c'est un **tuple** à un élément. `(name)` sans virgule n'est que `name` entre parenthèses, et sqlite3 tenterait de lire chaque lettre comme une valeur.
- `"--"` dit à `wc` que ce qui suit n'est plus une option. Sans lui, un fichier nommé `-c` serait pris pour l'option « compter les octets ».
- La requête paramétrée garde ses apostrophes : `o'brien` est cherché tel quel, sans échappement manuel.

## Défense en profondeur

La validation (accepter seulement ce qui est attendu, par liste blanche) réduit la surface, mais elle ne remplace pas les paramètres. Le compte de base de données de l'application doit en outre avoir le minimum de droits : un compte sans `DROP` rend l'injection moins destructrice.

!!Un compte applicatif qui peut tout faire sur la base transforme la moindre injection en catastrophe!!

## Pas à pas : corriger app.py

1. Repérez chaque endroit où une donnée externe est collée dans du texte : `+`, f-string, `format()`, `%`.
2. Dans `find_user`, remplacez la concaténation par `?` dans la requête, et passez `(name,)` en second argument de `execute`.
3. Dans `count_lines`, remplacez la chaîne par la liste `["wc", "-l", "--", path]` et supprimez `shell=True`.
4. Testez à la main dans `python3` : `find_user(conn, "' OR '1'='1")` doit renvoyer une liste vide, et `find_user(conn, "o'brien")` doit trouver o'brien.
5. Créez un fichier `"a b.txt"` et vérifiez que `count_lines("a b.txt")` fonctionne malgré l'espace.

**À retenir :** donnée externe, jamais du code ; paramètres liés pour SQL ; liste d'arguments sans shell pour les commandes ; moindre privilège sur la base.
