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

## Les deux fonctions corrigées

```python
# Fichier : web.py
import html
import os

def render_comment(author, text):
    return (
        "<div class='comment'>"
        "<b>" + html.escape(author) + "</b>"     # ← l'auteur aussi : c'est une donnée utilisateur
        "<p>" + html.escape(text) + "</p>"       # ← échappé au moment de l'insertion
        "</div>"
    )

def read_upload(base_dir, filename):
    base = os.path.realpath(base_dir)                         # 1. le dossier, liens résolus
    path = os.path.realpath(os.path.join(base, filename))     # 2. la cible, liens résolus
    if os.path.commonpath([base, path]) != base:              # 3. la cible est-elle DANS base ?
        raise ValueError("chemin en dehors du dossier autorisé")
    with open(path, encoding="utf-8") as f:                   # 4. seulement ensuite, on ouvre
        return f.read()
```

L'ordre des étapes de `read_upload` est la protection elle-même : on **résout**, on **vérifie**, et on **ouvre** en dernier. Ouvrir avant de vérifier, ou vérifier le nom avant de le résoudre, laisse passer un lien symbolique.

Ce que voit chaque attaque, avec `base_dir = /srv/uploads` :

| `filename` | `realpath` donne | `commonpath` | Résultat |
| --- | --- | --- | --- |
| `ok.txt` | `/srv/uploads/ok.txt` | `/srv/uploads` | lu |
| `../secret.txt` | `/srv/secret.txt` | `/srv` | refusé |
| `/etc/passwd` | `/etc/passwd` | `/` | refusé |
| `../uploads2/x` | `/srv/uploads2/x` | `/srv` | refusé, là où `startswith` aurait accepté |
| `lien` → `/etc` | `/etc` | `/` | refusé |

## Pas à pas : corriger web.py

1. Ajoutez `import html` et `import os` en haut du fichier.
2. Dans `render_comment`, entourez **chaque** donnée de `html.escape(...)`, l'auteur comme le texte.
3. Dans `read_upload`, écrivez les trois étapes dans l'ordre : `realpath` de la base, `realpath` de la cible, comparaison `commonpath`.
4. Levez `ValueError` si la comparaison échoue, et ouvrez le fichier seulement après.
5. Testez à la main : `render_comment("x", "<script>")` doit contenir `&lt;script&gt;`, et `read_upload(base, "../x")` doit lever l'exception.

**À retenir :** échapper à la sortie (`html.escape`), CSP en renfort ; résoudre le chemin (`realpath`) puis vérifier avec `commonpath`.
