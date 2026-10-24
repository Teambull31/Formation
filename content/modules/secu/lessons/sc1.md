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

## Défense en profondeur

La validation (accepter seulement ce qui est attendu, par liste blanche) réduit la surface, mais elle ne remplace pas les paramètres. Le compte de base de données de l'application doit en outre avoir le minimum de droits : un compte sans `DROP` rend l'injection moins destructrice.

!!Un compte applicatif qui peut tout faire sur la base transforme la moindre injection en catastrophe!!

**À retenir :** donnée externe, jamais du code ; paramètres liés pour SQL ; liste d'arguments sans shell pour les commandes ; moindre privilège sur la base.
