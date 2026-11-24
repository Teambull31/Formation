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

## Déplacer les tâches dans le rôle : ce qui change dans l'indentation

Dans un playbook, les tâches sont **sous** `tasks:`, lui-même sous le play. Dans `roles/nginx/tasks/main.yml`, il n'y a ni play ni clé `tasks:` : le fichier **est** directement la liste des tâches. Tout remonte donc de 4 espaces, et le tiret de chaque tâche passe en colonne 0.

```yaml
# AVANT : site.yml, les tâches sont à 4 espaces sous « tasks: »
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Installer les paquets de base
      ansible.builtin.apt:
        name: "{{ nginx_packages }}"
        state: present
```

```yaml
# APRÈS : roles/nginx/tasks/main.yml, la liste commence en colonne 0
---
- name: Installer les paquets de base
  ansible.builtin.apt:
    name: "{{ nginx_packages }}"
    state: present

- name: Configurer nginx
  ansible.builtin.template:
    src: nginx.conf.j2             # ← plus de « templates/ » : le rôle y cherche tout seul
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: "0644"
    validate: nginx -t -c %s
  notify: Recharger nginx          # handler défini dans roles/nginx/handlers/main.yml
```

```yaml
# roles/nginx/handlers/main.yml : même forme, une liste en colonne 0
---
- name: Recharger nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded
```

```yaml
# roles/nginx/defaults/main.yml : de simples variables, au niveau 0
---
nginx_port: 80
nginx_sites: []
nginx_packages: [nginx]
```

```yaml
# roles/nginx/meta/main.yml
---
galaxy_info:
  description: Installe et configure nginx.
  author: equipe-infra
  min_ansible_version: "2.15"
dependencies: []                   # ← niveau 0, à côté de galaxy_info
```

Le `---` en première ligne marque le début d'un document YAML. Il est facultatif, mais `ansible-lint` le demande : il signale qu'un fichier est bien du YAML et pas un fragment collé.

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

`roles:` est une clé du **play**, alignée sur `hosts:`. Chaque rôle est un élément de liste (`- role: nginx`), et `vars:` sous un rôle lui passe des valeurs, au niveau de `role:` (pas sous lui). Les rôles s'exécutent **avant** les `tasks:` du play, dans l'ordre de la liste : `common` d'abord, `nginx` ensuite.

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

## Pas à pas : extraire le rôle nginx

1. Créez le squelette : `ansible-galaxy role init roles/nginx`.
2. Copiez les tâches de `site.yml` dans `roles/nginx/tasks/main.yml`, puis retirez 4 espaces à chaque ligne : le tiret de chaque tâche arrive en colonne 0.
3. Déplacez `templates/nginx.conf.j2` dans `roles/nginx/templates/`, et écrivez `src: nginx.conf.j2` sans le dossier.
4. Mettez le handler dans `roles/nginx/handlers/main.yml`, en colonne 0 lui aussi.
5. Mettez `nginx_port` et `nginx_sites` dans `roles/nginx/defaults/main.yml`.
6. Remplissez `roles/nginx/meta/main.yml` : `galaxy_info:` avec une `description`.
7. Dans `site.yml`, supprimez `tasks:` et `handlers:`, et ajoutez `roles:` avec `- role: nginx`, aligné sur `hosts:`.
8. Ajoutez une `version` à chaque collection de `requirements.yml`.
9. Vérifiez : `ansible-playbook -i inventory.ini site.yml --list-tasks` doit lister les tâches préfixées par `nginx :`.

## Labo réel

```bash
ansible-galaxy role init /tmp/demo-role && find /tmp/demo-role
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --list-tasks
```

**À retenir :** un rôle par composant ; `tasks/main.yml` comme point d'entrée ; `defaults/` pour les réglages surchargeables, `vars/` pour les constantes ; variables préfixées par le nom du rôle ; playbook en `roles:` ; collections et rôles tiers dans `requirements.yml` avec versions ; un inventaire par environnement ; Molecule et `ansible-lint`.
