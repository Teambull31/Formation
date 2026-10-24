# Réseau, SSH et pare-feu

Un serveur exposé sur Internet est sondé en continu, parfois quelques minutes après sa mise en ligne. Trois réglages réduisent l'essentiel du risque : un SSH durci, des ports fermés par défaut, des services qui n'écoutent que là où il faut.

## Adresses, ports et DNS

Une machine est joignable par son adresse IP, et chaque service y écoute sur un **port** : 22 pour SSH, 80 pour HTTP, 443 pour HTTPS, 5432 pour PostgreSQL. Le **DNS** traduit un nom (`exemple.fr`) en adresse. `ss -tlnp` liste les ports ouverts en écoute, `dig exemple.fr` interroge le DNS, `curl -I https://exemple.fr` teste un service web.

## Durcir SSH

Le fichier `sshd_config` règle le serveur SSH. Quatre réglages comptent : `PermitRootLogin no` interdit la connexion directe en root, `PasswordAuthentication no` impose les clés SSH et rend les mots de passe devinables inutiles, `MaxAuthTries 3` limite les essais par connexion, `AllowUsers deploy` ne laisse entrer que les comptes listés.

!!Avant de couper l'authentification par mot de passe, vérifiez qu'une connexion par clé fonctionne dans un second terminal!!

Détail utile : pour chaque mot-clé, sshd retient la **première** valeur rencontrée. Une ligne `PermitRootLogin yes` placée avant votre `PermitRootLogin no` gagne.

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

`policy drop` rejette tout ce qui n'est pas autorisé. `ct state established,related accept` laisse passer les réponses aux connexions que la machine a ouvertes. L'interface `lo` est la boucle locale, indispensable aux services qui se parlent entre eux.

!!Une base de données n'a jamais sa place sur Internet : le port 5432 reste fermé au pare-feu et le service n'écoute que sur 127.0.0.1!!

## Écouter au bon endroit

Un service qui écoute sur `0.0.0.0` répond sur toutes les interfaces ; sur `127.0.0.1`, seulement à la machine elle-même. Le pare-feu est la deuxième barrière, pas la seule.

**À retenir :** ports et DNS, SSH sans root ni mot de passe, première valeur gagnante, pare-feu en refus par défaut, bases de données jamais exposées.
