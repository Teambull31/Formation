# Inventaire, commandes ad hoc et premier playbook

Terraform crée les machines. **Ansible** les configure : installer des paquets, déposer des fichiers, démarrer des services, sur une machine ou sur mille, de la même façon. Il se connecte en **SSH**, sans agent à installer sur les serveurs : il suffit de Python côté cible.

## Le vocabulaire

- **Nœud de contrôle** : la machine où l'on lance `ansible` (votre poste, ou une CI).
- **Hôtes gérés** : les serveurs configurés.
- **Inventaire** : la liste des hôtes, rangés en **groupes**.
- **Module** : une action unitaire (`ansible.builtin.apt`, `copy`, `service`, `user`).
- **Tâche** : un appel de module avec ses paramètres.
- **Playbook** : un fichier YAML qui associe des groupes d'hôtes à une liste de tâches.

## L'inventaire

Le format INI est le plus lisible :

```ini
[web]
web1 ansible_host=10.0.1.11
web2 ansible_host=10.0.1.12

[db]
db1 ansible_host=10.0.2.21

[prod:children]
web
db

[all:vars]
ansible_user=deploy
```

- `[web]` déclare un groupe ; une ligne = un hôte, avec des variables `clé=valeur`.
- `[prod:children]` : un groupe de groupes.
- `[all:vars]` : des variables pour tout le monde. `all` contient tous les hôtes.
- `ansible-inventory -i inventory.ini --graph` affiche l'arbre.

!!Ne mettez jamais un mot de passe dans l'inventaire : ansible_password en clair finit dans Git, utilisez des clés SSH!!

## Les commandes ad hoc

Pour une action ponctuelle, pas besoin de playbook :

```bash
ansible all -i inventory.ini -m ansible.builtin.ping
ansible web -i inventory.ini -m ansible.builtin.command -a "uptime"
ansible web -i inventory.ini -b -m ansible.builtin.apt -a "name=htop state=present"
```

`-m` choisit le module, `-a` ses arguments, `-b` (*become*) passe en root via sudo. `ping` ne fait pas un ping réseau : il vérifie la connexion SSH et Python.

## Le premier playbook

```yaml
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Installer nginx
      ansible.builtin.apt:
        name: nginx
        state: present
        update_cache: true
    - name: Démarrer nginx au boot
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true
```

## Les trois niveaux d'un playbook

Un playbook a toujours la même architecture, et chaque niveau d'indentation correspond à un étage :

```yaml
# Fichier : site.yml
- name: Serveurs web              # ÉTAGE PLAY : le tiret ouvre un play (colonne 0)
  hosts: web                      #   clés du play : alignées sur « name », 2 espaces
  become: true                    #   tout le play passe en root via sudo
  tasks:                          #   la liste des tâches du play
    - name: Installer nginx       # ÉTAGE TÂCHE : le tiret ouvre une tâche (4 espaces)
      ansible.builtin.apt:        #   le module : aligné sur le « name » de la tâche
        name: nginx               # ÉTAGE PARAMÈTRES : arguments DU MODULE (8 espaces)
        state: present
        update_cache: true
    - name: Démarrer nginx au boot   # tâche suivante : même colonne que la précédente
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true
```

- **Play** : `name`, `hosts`, `become`, `tasks` sont alignés, juste après le tiret du play.
- **Tâche** : `name` et le module (`ansible.builtin.apt:`) sont alignés, juste après le tiret de la tâche.
- **Paramètres** : `name: nginx`, `state: present` sont indentés **sous le module**, car ce sont ses arguments.

Le `name` apparaît trois fois avec trois sens : le nom du play, le nom de la tâche, et le paramètre `name` du module apt (le paquet). C'est le niveau d'indentation qui dit lequel est lequel.

```yaml
# FAUX : state est au niveau de la tâche, Ansible ne le passe pas au module
    - name: Installer nginx
      ansible.builtin.apt:
        name: nginx
      state: present          # ✗ « state » n'est pas un mot-clé de tâche : erreur

# JUSTE : state est un paramètre d'apt, sous le module
    - name: Installer nginx
      ansible.builtin.apt:
        name: nginx
        state: present
```

- Le fichier est une **liste de plays** ; chaque play vise des `hosts` et liste ses `tasks`.
- Chaque tâche a un `name` : c'est ce qu'on lit dans la sortie et dans les journaux.
- Écrivez le nom complet du module (**FQCN**) : `ansible.builtin.apt` et non `apt`. On sait d'où vient le code.

## Décrire l'état, pas les commandes

`ansible.builtin.apt` avec `state: present` vérifie d'abord : si nginx est installé, il ne fait rien et répond `ok`. Un `ansible.builtin.shell: apt-get install -y nginx` relance la commande à chaque fois et répond toujours `changed`. C'est la différence entre une configuration **idempotente** et un script.

!!Utiliser shell ou command pour ce qu'un module sait faire rend le playbook non idempotent et cache les vrais changements!!

## Lancer et lire

```bash
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --check --diff
ansible-playbook -i inventory.ini site.yml --limit web1
```

Le récapitulatif final, `PLAY RECAP`, donne par hôte : `ok`, `changed`, `unreachable`, `failed`. Un second lancement doit afficher `changed=0`.

!!--limit est votre ami : testez sur un seul hôte avant de lancer sur tout le parc!!

## Pas à pas : inventaire et premier playbook

1. Dans `inventory.ini`, écrivez `[web]` puis une ligne par hôte : `web1 ansible_host=10.0.1.11`. Faites de même pour `[db]`.
2. Ajoutez `[prod:children]` avec, en dessous, les noms des groupes `web` et `db` (pas des hôtes).
3. Ajoutez `[all:vars]` avec `ansible_user=deploy`, et supprimez toute ligne `ansible_password`.
4. Vérifiez l'arbre : `ansible-inventory -i inventory.ini --graph`.
5. Dans `site.yml`, écrivez le play en colonne 0 : `- name:`, puis `hosts: web`, `become: true` et `tasks:` alignés sur `name`.
6. Ajoutez la tâche apt : `- name: Installer nginx` à 4 espaces, `ansible.builtin.apt:` à 6, ses paramètres à 8.
7. Ajoutez la tâche service de la même façon, et supprimez toute tâche `shell` ou `command`.
8. Lancez `ansible-playbook -i inventory.ini site.yml --syntax-check`, puis `--check --diff` sur un hôte avec `--limit web1`.

## Labo réel

Ansible est installé sur votre poste. Dans le terminal du TP :

```bash
ansible localhost -c local -m ansible.builtin.setup -a "filter=ansible_distribution*"
ansible-inventory -i inventory.ini --graph
ansible-playbook -i inventory.ini site.yml --syntax-check
```

**À retenir :** sans agent, en SSH ; inventaire en groupes avec `:children` et `:vars` ; ad hoc avec `-m`, `-a`, `-b` ; playbook = liste de plays avec `hosts`, `become`, `tasks` nommées ; modules en FQCN ; `state:` plutôt que `shell` ; `--syntax-check`, `--check --diff`, `--limit`.
