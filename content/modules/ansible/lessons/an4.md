# Rôles, collections et structure de projet

Un playbook de 300 lignes qui fait tout est impossible à relire et à réutiliser. Un **rôle** range tout ce qu'il faut pour un composant (nginx, PostgreSQL, un utilisateur) dans une arborescence standard. Le playbook ne fait plus qu'assembler des rôles.

## L'arborescence d'un rôle

```
roles/nginx/
  tasks/main.yml       les tâches (point d'entrée)
  handlers/main.yml    les handlers
  defaults/main.yml    les valeurs par défaut (priorité la plus faible)
  vars/main.yml        des constantes internes (priorité forte)
  templates/           les fichiers .j2
  files/               les fichiers copiés tels quels
  meta/main.yml        description, plateformes, dépendances
```

`ansible-galaxy role init roles/nginx` crée ce squelette. Seuls les dossiers utilisés sont nécessaires, mais `tasks/main.yml` est le point d'entrée.

- Dans un rôle, `template: src: nginx.conf.j2` cherche automatiquement dans `roles/nginx/templates/`.
- Les handlers du rôle sont notifiables par ses tâches.

## defaults ou vars

Mettez **dans `defaults/main.yml`** tout ce que l'utilisateur du rôle peut vouloir changer : le port, la liste des sites. Ces valeurs ont la priorité la plus basse, donc un `group_vars/web.yml` les surcharge sans effort. `vars/main.yml` est réservé aux constantes internes qu'on ne veut pas voir surchargées.

!!Une valeur réglable mise dans vars/main.yml ne peut plus être surchargée par group_vars : l'utilisateur du rôle croira à un bug!!

!!Un rôle qui lit une variable sans valeur par défaut échoue sur le premier hôte qui ne la définit pas : tout réglage a sa ligne dans defaults!!

Préfixez les variables du rôle par son nom (`nginx_port`, `nginx_sites`) : deux rôles qui utiliseraient tous deux `port` se marcheraient dessus.

## Le playbook devient court

```yaml
- name: Serveurs web
  hosts: web
  become: true
  roles:
    - role: common
    - role: nginx
      vars:
        nginx_port: 8080
```

Ou au milieu de tâches : `ansible.builtin.import_role` (lu au démarrage, statique) et `ansible.builtin.include_role` (lu à l'exécution, peut être conditionnel ou en boucle).

## Collections et Galaxy

Les modules hors `ansible.builtin` vivent dans des **collections** : `community.general`, `community.postgresql`, `amazon.aws`. Les rôles et collections tiers se déclarent dans un fichier versionné :

```yaml
# requirements.yml
collections:
  - name: community.general
    version: "9.4.0"
  - name: community.postgresql
    version: "3.5.0"
roles:
  - name: geerlingguy.docker
    version: "7.4.1"
```

```bash
ansible-galaxy install -r requirements.yml
```

!!Une collection installée sans version épinglée peut changer de comportement entre deux machines ou deux semaines!!

## La structure d'un projet

```
ansible.cfg
inventories/
  prod/hosts.ini
  prod/group_vars/
  staging/hosts.ini
site.yml
requirements.yml
roles/
  common/
  nginx/
```

Un inventaire par environnement, avec ses `group_vars` : le même `site.yml` et les mêmes rôles servent partout, seules les valeurs changent. On lance `ansible-playbook -i inventories/staging site.yml`.

Un `ansible.cfg` à la racine fixe les réglages du projet :

```ini
[defaults]
inventory = inventories/staging
roles_path = roles
stdout_callback = yaml
```

## Tester un rôle

**Molecule** crée une machine jetable (conteneur), applique le rôle, vérifie l'idempotence (deuxième passage sans `changed`) et lance des tests. `ansible-lint` signale les mauvaises pratiques (module sans FQCN, `shell` évitable, tâche sans nom).

## Labo réel

```bash
ansible-galaxy role init /tmp/demo-role && find /tmp/demo-role
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --list-tasks
```

**À retenir :** un rôle par composant ; `tasks/main.yml` comme point d'entrée ; `defaults/` pour les réglages surchargeables, `vars/` pour les constantes ; variables préfixées par le nom du rôle ; playbook en `roles:` ; collections et rôles tiers dans `requirements.yml` avec versions ; un inventaire par environnement ; Molecule et `ansible-lint`.
