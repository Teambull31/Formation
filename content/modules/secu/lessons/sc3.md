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

**À retenir :** pas de mot de passe en clair, hachage lent et salé, `compare_digest`, secrets en variables d'environnement, échec explicite si le secret manque.
