# Utilisateurs, fichiers et permissions

Sur un serveur Linux, presque tout est un fichier, et chaque fichier a un propriétaire. Les droits d'accès sont la première barrière : un secret lisible par tout le monde n'est plus un secret.

## Lire la sortie de ls -l

```
-rwxr-x--- 1 deploy ops 420 mars 12 deploy.sh
```

Le premier caractère donne le type (`-` fichier, `d` dossier). Viennent ensuite trois groupes de trois lettres : les droits du **propriétaire** (`rwx`), du **groupe** (`r-x`) et des **autres** (`---`). `r` lit, `w` écrit, `x` exécute. Sur un dossier, `x` signifie « avoir le droit d'y entrer ».

## Écrire les droits en octal

Chaque droit vaut un nombre : `r` = 4, `w` = 2, `x` = 1. On additionne par groupe : `rwx` donne 7, `r-x` donne 5, `---` donne 0. Le mode `750` veut donc dire propriétaire `rwx`, groupe `r-x`, autres rien.

`chmod 600 secrets.env` réserve le fichier à son propriétaire. `chmod u+x deploy.sh` ajoute l'exécution pour le propriétaire seulement. `chown deploy:ops fichier` change le propriétaire et le groupe.

!!Ne tapez jamais chmod 777 pour « faire marcher » quelque chose : tout le monde peut alors lire, modifier et exécuter!!

## Le moindre privilège

Donnez à chaque compte seulement ce dont il a besoin. Un script de déploiement doit être exécutable par son propriétaire, jamais modifiable par les autres : sinon n'importe quel compte peut y glisser une commande qui sera lancée avec vos droits. Un dossier partagé par une équipe prend souvent le mode `770` : l'équipe y travaille, personne d'autre n'y entre.

## Root et sudo

Le compte **root** contourne tous les droits. On ne s'y connecte pas : on travaille avec un compte ordinaire et on élève un seul ordre avec `sudo`, ce qui laisse une trace dans les journaux.

!!Une application ne doit jamais tourner en root si un compte ordinaire suffit!!

!!Un fichier de mots de passe lisible par le groupe ou par tous est déjà une fuite : 600 par défaut!!

## Le masque umask

Quand un programme crée un fichier, `umask` retire des droits au mode de départ. Avec `umask 027`, un nouveau fichier est créé en `640` et un dossier en `750` : le groupe lit, les autres n'ont rien.

**À retenir :** lire `rwx`, calculer l'octal, `chmod` et `chown`, moindre privilège, secrets en `600`, root jamais en direct.
