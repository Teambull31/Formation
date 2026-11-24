# Processus, journaux et filtres en ligne de commande

Quand un serveur se comporte mal, la réponse est presque toujours dans un processus ou dans un journal. Savoir les interroger vite est le geste de base de l'exploitation.

## Les processus

Un **processus** est un programme en cours d'exécution, identifié par un numéro, le PID. `ps aux` les liste, `top` les suit en direct, `ss -tlnp` montre quels processus écoutent sur quel port. Pour arrêter un processus on lui envoie un **signal** : `kill PID` envoie `SIGTERM`, une demande polie qui laisse le programme se fermer proprement.

!!Essayez toujours SIGTERM avant SIGKILL : kill -9 coupe le programme net, sans lui laisser fermer ses fichiers!!

!!Ne supprimez jamais un journal pour libérer de la place sans l'avoir lu : il contient la trace de l'incident!!

## Les journaux

Les services écrivent dans `/var/log` et, avec systemd, dans le journal : `journalctl -u nginx --since "1 hour ago"` affiche les messages d'un service. `tail -f fichier` suit un fichier qui grossit.

## Les tubes et les filtres

Le tube `|` envoie la sortie d'une commande vers l'entrée de la suivante. Quelques filtres suffisent à répondre à presque toute question : `grep` garde les lignes qui contiennent un motif, `awk '{print $1}'` extrait une colonne, `sort` trie, `uniq -c` compte les lignes identiques consécutives, `head -3` garde les trois premières.

```bash
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -3
```

Cette ligne donne les trois adresses les plus fréquentes d'un journal web. Le premier `sort` regroupe les lignes identiques, car `uniq` ne compte que les voisines. Le second `sort -rn` classe par nombre, du plus grand au plus petit.

Voici ce qui sort de chaque étape, sur un petit journal de cinq lignes :

```
awk '{print $1}'   →  10.0.0.5     sort   →  10.0.0.5     uniq -c  →  3 10.0.0.5
                      10.0.0.9                10.0.0.5                 2 10.0.0.9
                      10.0.0.5                10.0.0.5
                      10.0.0.9                10.0.0.9     sort -rn → classe par le nombre
                      10.0.0.5                10.0.0.9     head -3  → garde les 3 premières
```

Construisez un tube **une étape à la fois** : lancez `awk '{print $1}' access.log | head`, regardez, ajoutez `| sort`, regardez, et ainsi de suite. On voit tout de suite l'étape qui ne fait pas ce qu'on croit.

!!uniq ne fonctionne qu'après un sort : sans tri, les doublons éloignés ne sont pas comptés ensemble!!

## Le script complet

```bash
#!/usr/bin/env bash
# Fichier : top_ips.sh   Usage : bash top_ips.sh access.log
set -euo pipefail                 # 1re ligne utile : arrêt à la première erreur

log="$1"                          # le journal reçu en premier argument

awk '{print $1}' "$log" \
  | sort \
  | uniq -c \
  | sort -rn \
  | head -3 \
  | awk '{print $1, $2}'          # « 3 10.0.0.5 » : retire les espaces de uniq -c
```

- `#!/usr/bin/env bash` : la première ligne dit quel interpréteur lance le fichier.
- `set -euo pipefail` : `-e` arrête au premier échec, `-u` refuse une variable non définie, `pipefail` fait échouer le tube si une étape échoue.
- `"$log"` entre guillemets : un nom de fichier avec une espace reste un seul argument.
- `\` en fin de ligne continue la commande ; on met un `|` par ligne pour lire le tube de haut en bas.
- Le dernier `awk` normalise la sortie : `uniq -c` aligne les nombres avec des espaces au début.

Pour les erreurs serveur, le statut est le champ 9 :

```bash
awk '$9 >= 500 {n++} END {print n+0}' "$1"
#    └─ condition  └─ action   └─ après la dernière ligne : n+0 affiche 0 si rien
```

## Lire un journal d'accès web

Chaque ligne a la forme `IP - - [date] "GET /page HTTP/1.1" statut octets`. Avec `awk`, le champ 1 est l'adresse et le champ 9 le code de statut. Un statut 5xx signale une erreur du serveur, 4xx une erreur du client.

## Pas à pas : les deux scripts du TP

1. Regardez trois lignes du journal : `head -3 access.log`. Repérez le champ 1 (adresse) et le champ 9 (statut).
2. Construisez le tube des adresses étape par étape dans le terminal, avec `head` à la fin de chaque essai.
3. Quand le résultat est bon, recopiez-le dans `top_ips.sh`, en remplaçant `access.log` par `"$1"`.
4. Testez : `bash top_ips.sh access.log`. Trois lignes, la plus fréquente d'abord.
5. Écrivez `errors_5xx.sh` avec le `awk` à condition. Testez : un seul nombre.
6. Vérifiez sur un autre journal que la réponse n'est pas écrite en dur : `head -50 access.log > petit.log && bash errors_5xx.sh petit.log`.

**À retenir :** PID et signaux, `journalctl`, tubes, `grep`/`awk`/`sort`/`uniq`, SIGTERM avant SIGKILL, trier avant de compter.
