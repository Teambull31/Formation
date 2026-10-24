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

!!uniq ne fonctionne qu'après un sort : sans tri, les doublons éloignés ne sont pas comptés ensemble!!

## Lire un journal d'accès web

Chaque ligne a la forme `IP - - [date] "GET /page HTTP/1.1" statut octets`. Avec `awk`, le champ 1 est l'adresse et le champ 9 le code de statut. Un statut 5xx signale une erreur du serveur, 4xx une erreur du client.

**À retenir :** PID et signaux, `journalctl`, tubes, `grep`/`awk`/`sort`/`uniq`, SIGTERM avant SIGKILL, trier avant de compter.
