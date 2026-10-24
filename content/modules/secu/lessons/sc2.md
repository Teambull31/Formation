# XSS et traversée de chemin

Deux autres familles très répandues : faire exécuter du code par le navigateur d'un visiteur, et lire un fichier que l'on ne devait pas pouvoir lire.

## Le XSS (cross-site scripting)

Quand une page affiche un texte écrit par un utilisateur sans l'avoir échappé, le navigateur le lit comme du HTML.

```python
return "<p>" + text + "</p>"
```

Un commentaire contenant `<script>` ou `<img src=x onerror=...>` s'exécute dans le navigateur de chaque lecteur, avec ses droits sur le site : vol de session, actions en son nom, faux formulaires.

La parade est l'**échappement à la sortie** : remplacer `<`, `>`, `&` et les guillemets par leurs entités HTML. En Python : `html.escape(text)`.

!!Échappez toute donnée venue d'un utilisateur au moment de l'insérer dans la page, y compris les noms et les titres!!

Les guillemets comptent aussi : une valeur placée dans un attribut (`value="..."`) peut en sortir avec un `"` et ajouter `onmouseover=...`. Un en-tête **Content-Security-Policy** ajoute une seconde barrière en interdisant les scripts en ligne, mais ne dispense pas d'échapper.

## La traversée de chemin

```python
open(base_dir + "/" + filename)
```

Avec `filename = "../secret.txt"`, le chemin sort du dossier prévu. Avec un chemin absolu, `os.path.join(base, "/etc/passwd")` ignore même la base. Un lien symbolique placé dans le dossier peut aussi mener ailleurs.

## La parade : résoudre puis vérifier

On calcule le chemin réel, liens suivis (`os.path.realpath`), puis on vérifie qu'il reste dans le dossier autorisé.

```python
base = os.path.realpath(base_dir)
path = os.path.realpath(os.path.join(base, filename))
if os.path.commonpath([base, path]) != base:
    raise ValueError("chemin en dehors du dossier autorisé")
```

!!Ne vérifiez pas avec path.startswith(base) : /uploads2/x commence par /uploads sans être dedans!!

!!Ne cherchez pas à retirer les « ../ » du nom : les variantes encodées passent à travers, résolvez et comparez!!

**À retenir :** échapper à la sortie (`html.escape`), CSP en renfort ; résoudre le chemin (`realpath`) puis vérifier avec `commonpath`.
