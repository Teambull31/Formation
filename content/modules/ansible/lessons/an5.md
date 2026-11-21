# Ansible Vault et sécurité

Un playbook de base de données a besoin d'un mot de passe. Il ne doit apparaître ni dans Git en clair, ni dans les journaux d'exécution. **Ansible Vault** chiffre les fichiers sensibles ; quelques réglages empêchent les fuites à l'exécution.

## Chiffrer avec ansible-vault

```bash
ansible-vault create group_vars/db/vault.yml    # crée et ouvre l'éditeur
ansible-vault encrypt group_vars/db/vault.yml   # chiffre un fichier existant
ansible-vault view group_vars/db/vault.yml
ansible-vault edit group_vars/db/vault.yml
ansible-vault rekey group_vars/db/vault.yml     # changer le mot de passe du coffre
```

Un fichier chiffré commence par `$ANSIBLE_VAULT;1.1;AES256` suivi de lignes hexadécimales. Il se versionne sans risque : sans le mot de passe du coffre, il est illisible.

Au lancement : `--ask-vault-pass`, ou `--vault-password-file ~/.vault_pass` (un fichier hors du dépôt, en `chmod 600`). En CI, le mot de passe du coffre est un secret de la CI.

!!Le fichier de mot de passe du coffre ne se versionne jamais : ajoutez-le au .gitignore et rangez-le hors du dépôt!!

## Le motif vars / vault

On sépare la variable lisible de sa valeur secrète :

```yaml
# group_vars/db/vars.yml : en clair, lisible en revue
db_name: app
db_user: app
db_password: "{{ vault_db_password }}"
```

```yaml
# group_vars/db/vault.yml : chiffré
vault_db_password: "S3cr3t-tres-long"
```

On voit dans `vars.yml` quelles variables existent et d'où vient leur valeur, sans ouvrir le coffre. `grep -r vault_` liste tous les secrets du projet.

## Ne rien laisser fuir à l'exécution

Une tâche qui manipule un secret l'affiche en cas d'erreur ou en mode verbeux (`-v`). `no_log: true` masque ses paramètres et son résultat :

```yaml
    - name: Créer l'utilisateur de la base
      community.postgresql.postgresql_user:
        name: "{{ db_user }}"
        password: "{{ db_password }}"
      no_log: true
```

!!Sans no_log: true, un échec de la tâche imprime le mot de passe dans la sortie, puis dans les journaux de la CI!!

## La connexion SSH

- Authentification par **clé SSH**, jamais `ansible_password` en clair.
- `host_key_checking = False` désactive la vérification de l'empreinte du serveur : un attaquant au milieu peut se faire passer pour lui. Gardez la vérification ; alimentez `known_hosts` (`ssh-keyscan`, ou à la création des machines).
- Un utilisateur dédié (`deploy`) avec sudo, plutôt que root en SSH.

## become avec discernement

!!become: true sur tout le play donne root à chaque tâche, y compris celles qui n'en ont aucun besoin!!

`become: true` au niveau du play exécute **tout** en root. Préférez-le au niveau des tâches qui en ont besoin, ou `become_user: postgres` pour agir en tant qu'un compte précis.

## Les autres sources de secrets

Vault convient à une petite équipe. À plus grande échelle, on lit les secrets au moment de l'exécution depuis un gestionnaire : `community.hashi_vault.vault_kv2_get` (HashiCorp Vault), `amazon.aws.secretsmanager_secret` (lookup AWS). Le secret ne vit alors même plus dans le dépôt, chiffré ou non.

## Labo réel

```bash
echo 'vault_db_password: "essai"' > /tmp/v.yml
ansible-vault encrypt /tmp/v.yml && head -1 /tmp/v.yml
ansible-vault view /tmp/v.yml
```

Pour le TP, chiffrez votre `vault.yml` de la même façon : le contrôle vérifie l'en-tête du coffre.

**À retenir :** `ansible-vault encrypt`, `view`, `edit`, `rekey` ; en-tête `$ANSIBLE_VAULT;1.1;AES256` ; motif `vars.yml` lisible + `vault.yml` chiffré avec préfixe `vault_` ; mot de passe du coffre hors dépôt ; `no_log: true` sur les tâches sensibles ; clés SSH et vérification des empreintes ; `become` au plus près.
