# Utilisateurs, fichiers et permissions

Sur un serveur Linux, presque tout est un fichier, et chaque fichier a un propriétaire. Les droits d'accès sont la première barrière : un secret lisible par tout le monde n'est plus un secret.

## Lire la sortie de ls -l

```
-rwxr-x--- 1 deploy ops 420 mars 12 deploy.sh
```

Le premier caractère donne le type (`-` fichier, `d` dossier). Viennent ensuite trois groupes de trois lettres : les droits du **propriétaire** (`rwx`), du **groupe** (`r-x`) et des **autres** (`---`). `r` lit, `w` écrit, `x` exécute. Sur un dossier, `x` signifie « avoir le droit d'y entrer ».

Découpage de la ligne, colonne par colonne :

```
-rwxr-x---  1  deploy  ops  420  mars 12  deploy.sh
│└┬┘└┬┘└┬┘     │       │    │    │        └─ nom
│ │  │  │      │       │    │    └─ date de modification
│ │  │  │      │       │    └─ taille en octets
│ │  │  │      │       └─ groupe propriétaire
│ │  │  │      └─ utilisateur propriétaire
│ │  │  └─ autres : ---  (rien)
│ │  └─ groupe : r-x     (lire, exécuter)
│ └─ propriétaire : rwx  (lire, écrire, exécuter)
└─ type : - fichier, d dossier, l lien
```

## Écrire les droits en octal

Chaque droit vaut un nombre : `r` = 4, `w` = 2, `x` = 1. On additionne par groupe : `rwx` donne 7, `r-x` donne 5, `---` donne 0. Le mode `750` veut donc dire propriétaire `rwx`, groupe `r-x`, autres rien.

Le calcul, posé une fois pour toutes :

| Mode | Propriétaire | Groupe | Autres | Usage typique |
| --- | --- | --- | --- | --- |
| `600` | `rw-` (4+2) | `---` | `---` | secrets, clés privées |
| `640` | `rw-` | `r--` (4) | `---` | configuration lue par un service du groupe |
| `644` | `rw-` | `r--` | `r--` | fichier public ordinaire |
| `750` | `rwx` (4+2+1) | `r-x` (4+1) | `---` | script réservé à l'équipe |
| `770` | `rwx` | `rwx` | `---` | dossier de travail d'équipe |

L'ordre des trois chiffres est toujours le même : propriétaire, groupe, autres. `chmod 057` ne veut **pas** dire la même chose que `chmod 750`.

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

## Pas à pas : régler les droits du TP

1. Regardez l'état de départ : `ls -l` pour les fichiers, `ls -ld shared` pour le dossier lui-même (sans `-d`, `ls` liste son contenu).
2. Secrets : `chmod 600 secrets.env`. Relisez : `-rw-------`.
3. Script : `chmod 750 deploy.sh`. Relisez : `-rwxr-x---`. Le groupe peut lancer le script, pas le modifier.
4. Dossier : `chmod 770 shared`. Relisez avec `ls -ld shared` : `drwxrwx---`.
5. Vérifiez qu'aucun fichier n'est modifiable par les autres : `find . -perm -o+w` ne doit rien afficher.

**À retenir :** lire `rwx`, calculer l'octal, `chmod` et `chown`, moindre privilège, secrets en `600`, root jamais en direct.
