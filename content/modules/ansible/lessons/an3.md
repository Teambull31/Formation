# Templates Jinja2, boucles et conditions

Un fichier de configuration identique sur tous les serveurs est rare : le port change, la liste des sites change, la mémoire disponible change. Les **templates** génèrent chaque fichier à partir de variables, les **boucles** et **conditions** adaptent les tâches à chaque hôte.

## Les trois fichiers et leurs liens

```
projet/
├── site.yml                  ← le playbook : QUOI faire
├── group_vars/
│   └── web.yml               ← les données : nginx_port, nginx_sites, base_packages, admins
└── templates/
    └── nginx.conf.j2         ← le modèle : à quoi ressemble le fichier final
```

Le playbook ne contient aucune valeur : il lit `group_vars/web.yml`, et le template lit les mêmes variables.

```yaml
# Fichier : group_vars/web.yml
nginx_port: 8080
nginx_sites:                     # une liste d'objets : chaque site a un nom et un domaine
  - name: shop
    domain: shop.example.test
  - name: blog
    domain: blog.example.test
base_packages: [nginx, curl, ufw]
admins:
  - { name: alice, groups: sudo }
  - { name: bob, groups: sudo }
```

## Le playbook complet, ligne par ligne

```yaml
# Fichier : site.yml
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Installer les paquets de base
      ansible.builtin.apt:
        name: "{{ base_packages }}"     # la liste entière, en une seule transaction
        state: present
      when: ansible_os_family == "Debian"   # ← mot-clé de TÂCHE : aligné sur le module

    - name: Créer les comptes administrateurs
      ansible.builtin.user:
        name: "{{ item.name }}"          # item = l'élément courant de la boucle
        groups: "{{ item.groups }}"
        shell: /bin/bash
      loop: "{{ admins }}"               # ← mot-clé de TÂCHE : aligné sur le module
      loop_control:
        label: "{{ item.name }}"         # affiche « alice » au lieu de tout l'objet

    - name: Configurer nginx
      ansible.builtin.template:
        src: templates/nginx.conf.j2     # relatif au playbook
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: "0644"
        validate: nginx -t -c %s         # ← paramètre DU MODULE : sous template
      notify: Recharger nginx            # ← mot-clé de TÂCHE

  handlers:
    - name: Recharger nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

`when` et `loop` sont des mots-clés de **tâche** : ils décident si et combien de fois la tâche tourne, quel que soit le module. Ils s'alignent donc sur `name:` et sur le module. `validate`, au contraire, est propre au module `template` : il va dessous.

Un `when` placé sous le module est lu comme un paramètre inconnu, et Ansible répond `Unsupported parameters for (ansible.builtin.apt) module: when`.

## Le module template

`validate` teste le fichier généré **avant** de le mettre en place : `%s` est remplacé par un fichier temporaire. Si `nginx -t` échoue, l'ancien fichier reste et la tâche échoue. Le serveur ne redémarre jamais avec une configuration cassée.

!!Sans validate, une erreur dans un template déposée sur tout le parc fait tomber nginx partout au rechargement!!

## La syntaxe Jinja2

```jinja
# Géré par Ansible : toute modification à la main sera écrasée
worker_processes {{ ansible_processor_vcpus | default(2) }};
http {
{% for site in nginx_sites %}
  server {
    listen {{ nginx_port }};
    server_name {{ site.domain }};
    root /var/www/{{ site.name }};
  }
{% endfor %}
}
```

- `{{ variable }}` affiche une valeur.
- `{% for %}...{% endfor %}` et `{% if %}...{% endif %}` contrôlent la structure.
- Les **filtres** transforment : `default(2)`, `upper`, `join(", ")`, `to_nice_json`, `b64encode`.
- Une ligne d'en-tête « Géré par Ansible » prévient les collègues qui ouvriraient le fichier.

Ce que produit le template avec les données ci-dessus, sur une machine à 4 cœurs :

```nginx
# Géré par Ansible : toute modification à la main sera écrasée
worker_processes 4;
http {
  server {
    listen 8080;
    server_name shop.example.test;
    root /var/www/shop;
  }
  server {
    listen 8080;
    server_name blog.example.test;
    root /var/www/blog;
  }
}
```

Le bloc entre `{% for %}` et `{% endfor %}` est répété une fois par site. Les lignes `{% %}` elles-mêmes ne produisent rien. Dans un template, l'indentation n'a pas de sens pour Jinja2 : c'est seulement celle du fichier produit, à soigner pour qu'il reste lisible.

## Les boucles

- `loop:` répète la tâche pour chaque élément, lu par `item`. Les anciens `with_items` fonctionnent encore mais `loop` est la forme actuelle.
- Beaucoup de modules acceptent directement une liste (`apt: name:`) : une seule transaction, bien plus rapide qu'une boucle.
- `loop_control: label: "{{ item.name }}"` raccourcit l'affichage.

!!Une boucle qui installe un paquet à la fois lance apt dix fois : passez la liste entière au module quand il l'accepte!!

## Les conditions

`when:` est une expression Jinja2 **sans** accolades. On combine avec `and`, `or`, ou une liste (toutes vraies). Usages fréquents : selon l'OS, selon un groupe (`"web" in group_names`), selon le résultat d'une tâche précédente.

```yaml
# FAUX : accolades, la condition devient un texte
      when: "{{ ansible_os_family == 'Debian' }}"
# JUSTE : une expression nue
      when: ansible_os_family == "Debian"
# JUSTE : plusieurs conditions, toutes vraies
      when:
        - ansible_os_family == "Debian"
        - "'web' in group_names"
```

!!Des accolades dans when transforment la condition en chaîne de caractères : elle peut être toujours vraie!!

## Enregistrer un résultat

```yaml
    - name: Tester l'application
      ansible.builtin.uri:
        url: "http://localhost:{{ nginx_port }}/health"
        status_code: 200
      register: health          # mots-clés de tâche, alignés sur le module
      retries: 5
      delay: 3
      until: health.status == 200
```

`register` garde le résultat dans une variable ; `until`, `retries` et `delay` attendent qu'un service soit prêt. `ansible.builtin.debug: var=health` affiche son contenu.

## Pas à pas : moderniser le playbook

1. Créez `templates/nginx.conf.j2`. Ligne 1 : l'en-tête `# Géré par Ansible`. Puis un bloc `server` entre `{% for site in nginx_sites %}` et `{% endfor %}`.
2. Dans ce bloc, utilisez `{{ nginx_port }}` et `{{ site.domain }}`.
3. Dans `site.yml`, remplacez la boucle d'installation par une seule tâche apt avec `name: "{{ base_packages }}"`.
4. Sur cette tâche, ajoutez `when: ansible_os_family == "Debian"`, aligné sur `ansible.builtin.apt:`.
5. Remplacez la création de comptes en `shell` par `ansible.builtin.user` avec `name: "{{ item.name }}"`, et `loop: "{{ admins }}"` aligné sur le module.
6. Remplacez le dépôt de configuration par `ansible.builtin.template`, avec `owner`, `group`, `mode`, `validate` sous le module et `notify` aligné sur lui.
7. Testez le rendu en local (labo ci-dessous) et relisez le fichier produit.

## Labo réel

Testez un template sur votre poste, sans serveur :

```bash
ansible localhost -c local -m ansible.builtin.template \
  -a "src=templates/nginx.conf.j2 dest=/tmp/nginx.test.conf" \
  -e @group_vars/web.yml
cat /tmp/nginx.test.conf
```

**À retenir :** `template` avec `validate` et `%s` ; Jinja2 `{{ }}`, `{% for %}`, filtres et `default` ; en-tête « Géré par Ansible » ; `loop` et `item`, ou une liste passée au module ; `when` sans accolades et aligné sur le module ; `register`, `until`, `retries`.
