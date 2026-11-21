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

## Labo réel

Ansible est installé sur votre poste. Dans le terminal du TP :

```bash
ansible localhost -c local -m ansible.builtin.setup -a "filter=ansible_distribution*"
ansible-inventory -i inventory.ini --graph
ansible-playbook -i inventory.ini site.yml --syntax-check
```

**À retenir :** sans agent, en SSH ; inventaire en groupes avec `:children` et `:vars` ; ad hoc avec `-m`, `-a`, `-b` ; playbook = liste de plays avec `hosts`, `become`, `tasks` nommées ; modules en FQCN ; `state:` plutôt que `shell` ; `--syntax-check`, `--check --diff`, `--limit`.
