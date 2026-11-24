# Mots de passe, secrets et configuration

Une application qui résiste aux injections perd quand même tout si ses mots de passe sont lisibles ou si sa clé secrète traîne dans le dépôt. Trois règles couvrent l'essentiel.

## Ne jamais stocker un mot de passe

Si la base fuit (ce qui arrive), chaque mot de passe en clair est immédiatement utilisable, y compris sur d'autres sites, car les gens réutilisent leurs mots de passe. On stocke donc une **empreinte** du mot de passe, impossible à inverser, et on compare les empreintes.

## Un hachage lent et salé

Un hachage rapide comme MD5, SHA-1 ou un simple SHA-256 se calcule des milliards de fois par seconde sur une carte graphique : un attaquant essaie tous les mots de passe courants en quelques heures. On utilise une fonction conçue pour être **lente** et gourmande en mémoire : `scrypt`, `argon2`, `bcrypt` ou `pbkdf2_hmac`.

Le **sel** est une valeur aléatoire propre à chaque utilisateur, stockée avec l'empreinte. Deux comptes avec le même mot de passe obtiennent des empreintes différentes, et les tables précalculées deviennent inutiles.

```python
salt = os.urandom(16)
digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
```

!!Ne fabriquez jamais votre propre schéma de hachage rapide : utilisez scrypt, argon2 ou bcrypt avec un sel aléatoire!!

!!Ne journalisez jamais un mot de passe, même erroné : les journaux sont lus par plus de monde que la base!!

## Comparer sans fuite

Une comparaison `==` s'arrête au premier octet différent : le temps de réponse révèle la longueur du préfixe correct. `hmac.compare_digest` prend le même temps quel que soit le résultat.

## Les secrets hors du code

Une clé secrète écrite dans le code est copiée dans chaque clone, chaque sauvegarde et chaque conteneur. On la lit dans une **variable d'environnement** ou un gestionnaire de secrets, et on échoue explicitement si elle manque : mieux vaut un service qui refuse de démarrer qu'un service qui tourne avec une clé par défaut connue de tous.

!!Un secret versionné est compromis dès le premier commit, même supprimé ensuite : changez-le!!

## Le reste de la liste OWASP

Mettre à jour les dépendances (`pip-audit` signale les versions vulnérables), journaliser les connexions échouées sans y écrire les mots de passe, limiter les tentatives. Aucune de ces mesures ne remplace les autres.

## Le module corrigé, en entier

```python
# Fichier : auth.py
import hashlib
import hmac
import os

N, R, P = 2**14, 8, 1          # coût de scrypt : en constantes, pour les changer en un seul endroit

def _digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P)

def register(users, name, password):
    if len(password) < 8:                          # 1. valider d'abord : rien n'est stocké
        raise ValueError("mot de passe trop court")
    salt = os.urandom(16)                          # 2. un sel neuf, aléatoire, par compte
    users[name] = {"salt": salt, "hash": _digest(password, salt)}   # 3. sel + empreinte, jamais le mot de passe

def check(users, name, password):
    user = users.get(name)                         # .get : None si inconnu, pas d'exception
    if user is None:
        return False
    return hmac.compare_digest(                    # comparaison en temps constant
        user["hash"], _digest(password, user["salt"])   # on rehache avec LE sel stocké
    )

def get_secret_key():
    key = os.environ.get("APP_SECRET_KEY")
    if not key:                                    # absent ou vide : on refuse de continuer
        raise RuntimeError("APP_SECRET_KEY manquante")
    return key
```

Le trajet d'une vérification : au login, on reprend le **sel stocké** du compte, on recalcule l'empreinte du mot de passe tapé avec ce sel, puis on compare les deux empreintes. Le mot de passe d'origine n'est jamais relu, puisqu'il n'est stocké nulle part.

## Pas à pas : sécuriser auth.py

1. Supprimez toute ligne qui stocke `password` tel quel, et la constante `dev-secret-123`.
2. Écrivez `_digest` avec `hashlib.scrypt`, puis `register` dans l'ordre : valider la longueur, tirer le sel, stocker sel et empreinte.
3. Écrivez `check` : `users.get(name)`, `False` si absent, sinon `hmac.compare_digest` avec l'empreinte recalculée.
4. Écrivez `get_secret_key` avec `os.environ.get` et une exception si la valeur manque.
5. Testez : deux comptes au même mot de passe doivent avoir des `hash` différents.
6. Lancez l'application sans `APP_SECRET_KEY` : elle doit refuser de démarrer, avec un message clair.

**À retenir :** pas de mot de passe en clair, hachage lent et salé, `compare_digest`, secrets en variables d'environnement, échec explicite si le secret manque.
