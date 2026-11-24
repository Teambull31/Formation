# Réseau, SSH et pare-feu

Un serveur exposé sur Internet est sondé en continu, parfois quelques minutes après sa mise en ligne. Trois réglages réduisent l'essentiel du risque : un SSH durci, des ports fermés par défaut, des services qui n'écoutent que là où il faut.

## Adresses, ports et DNS

Une machine est joignable par son adresse IP, et chaque service y écoute sur un **port** : 22 pour SSH, 80 pour HTTP, 443 pour HTTPS, 5432 pour PostgreSQL. Le **DNS** traduit un nom (`exemple.fr`) en adresse. `ss -tlnp` liste les ports ouverts en écoute, `dig exemple.fr` interroge le DNS, `curl -I https://exemple.fr` teste un service web.

## Durcir SSH

Le fichier `sshd_config` règle le serveur SSH. Quatre réglages comptent : `PermitRootLogin no` interdit la connexion directe en root, `PasswordAuthentication no` impose les clés SSH et rend les mots de passe devinables inutiles, `MaxAuthTries 3` limite les essais par connexion, `AllowUsers deploy` ne laisse entrer que les comptes listés.

!!Avant de couper l'authentification par mot de passe, vérifiez qu'une connexion par clé fonctionne dans un second terminal!!

Détail utile : pour chaque mot-clé, sshd retient la **première** valeur rencontrée. Une ligne `PermitRootLogin yes` placée avant votre `PermitRootLogin no` gagne.

Le fichier n'a ni indentation ni sections : une ligne par réglage, `MotClé valeur`, séparés par une espace. Ce qui compte, c'est l'ordre et l'absence de doublon.

```
# Fichier : /etc/ssh/sshd_config
# Réglages de sécurité EN HAUT : la première valeur rencontrée gagne
PermitRootLogin no              # pas de connexion directe en root
PasswordAuthentication no       # clés SSH obligatoires
PubkeyAuthentication yes        # …et donc acceptées
MaxAuthTries 3                  # 3 essais par connexion
X11Forwarding no                # pas d'affichage graphique transporté
AllowUsers deploy               # liste blanche : les autres comptes sont refusés

# Le reste de la configuration d'origine peut suivre
```

```
# FAUX : la ligne du haut gagne, root peut toujours se connecter
PermitRootLogin yes
PermitRootLogin no

# JUSTE : une seule ligne par mot-clé
PermitRootLogin no
```

Après modification, testez la syntaxe **avant** de recharger : `sudo sshd -t` ne dit rien si le fichier est valide. Puis `sudo systemctl reload sshd`, et testez une nouvelle connexion dans un second terminal.

!!Un pare-feu mal réglé peut vous enfermer dehors : gardez toujours une session ouverte pendant que vous testez!!

## Le pare-feu : refuser par défaut

Un pare-feu filtre les paquets entrants. La bonne politique est de tout refuser puis d'autoriser au cas par cas. Avec nftables :

```
table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;
    ct state established,related accept
    iif "lo" accept
    tcp dport { 22, 443 } accept
  }
}
```

nftables structure avec des **accolades**, comme Terraform : une table contient des chaînes, une chaîne contient des règles. L'indentation n'est que de la lecture.

```
table inet filter {                          # table : « inet » = IPv4 et IPv6 ensemble
  chain input {                              # chaîne : le trafic qui ENTRE
    type filter hook input priority 0; policy drop;   # 1re ligne : le réglage de la chaîne
    ct state established,related accept      # règle 1 : les réponses à nos connexions
    iif "lo" accept                          # règle 2 : la boucle locale
    tcp dport { 22, 443 } accept             # règle 3 : SSH et HTTPS, rien d'autre
  }                                          # fin : tout le reste tombe sur policy drop
}
```

Les règles sont lues **de haut en bas**, et la première qui correspond décide. `established,related` est en tête car c'est le cas le plus fréquent : chaque réponse à une connexion sortante passe ici sans lire la suite. La politique `drop` ne s'applique qu'au paquet qui n'a trouvé aucune règle.

Pour retirer le port de la base, on l'enlève de l'ensemble `{ 22, 443 }` : pas besoin de règle `drop` pour 5432, la politique s'en charge.

Testez avant d'appliquer : `sudo nft -c -f firewall.nft` vérifie la syntaxe sans rien charger.

`policy drop` rejette tout ce qui n'est pas autorisé. `ct state established,related accept` laisse passer les réponses aux connexions que la machine a ouvertes. L'interface `lo` est la boucle locale, indispensable aux services qui se parlent entre eux.

!!Une base de données n'a jamais sa place sur Internet : le port 5432 reste fermé au pare-feu et le service n'écoute que sur 127.0.0.1!!

## Écouter au bon endroit

Un service qui écoute sur `0.0.0.0` répond sur toutes les interfaces ; sur `127.0.0.1`, seulement à la machine elle-même. Le pare-feu est la deuxième barrière, pas la seule.

## Pas à pas : durcir le TP

1. Ouvrez `sshd_config`. Cherchez chaque mot-clé avec `grep -n "PermitRootLogin\|PasswordAuthentication" sshd_config` : repérez les doublons.
2. Supprimez les doublons, puis placez les six réglages de sécurité en haut du fichier.
3. Ouvrez `firewall.nft`. Dans la chaîne `input`, mettez `policy drop;` sur la ligne `type filter hook input`.
4. Vérifiez la présence des règles `established,related` et `lo`, dans cet ordre, avant les ports.
5. Réduisez l'ensemble des ports à `{ 22, 443 }`.
6. Si les outils sont installés : `sshd -t -f sshd_config` et `nft -c -f firewall.nft`.

**À retenir :** ports et DNS, SSH sans root ni mot de passe, première valeur gagnante, pare-feu en refus par défaut, bases de données jamais exposées.
