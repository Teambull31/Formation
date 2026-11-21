# Templates Jinja2, boucles et conditions

Un fichier de configuration identique sur tous les serveurs est rare : le port change, la liste des sites change, la mémoire disponible change. Les **templates** génèrent chaque fichier à partir de variables, les **boucles** et **conditions** adaptent les tâches à chaque hôte.

## Le module template

```yaml
    - name: Configurer nginx
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: "0644"
        validate: nginx -t -c %s
      notify: Recharger nginx
```

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

## Les boucles

```yaml
    - name: Installer les paquets de base
      ansible.builtin.apt:
        name: "{{ base_packages }}"
        state: present
    - name: Créer les comptes
      ansible.builtin.user:
        name: "{{ item.name }}"
        groups: "{{ item.groups }}"
        shell: /bin/bash
      loop: "{{ admins }}"
```

- `loop:` répète la tâche pour chaque élément, lu par `item`. Les anciens `with_items` fonctionnent encore mais `loop` est la forme actuelle.
- Beaucoup de modules acceptent directement une liste (`apt: name:`) : une seule transaction, bien plus rapide qu'une boucle.
- `loop_control: label: "{{ item.name }}"` raccourcit l'affichage.

!!Une boucle qui installe un paquet à la fois lance apt dix fois : passez la liste entière au module quand il l'accepte!!

## Les conditions

```yaml
    - name: Pare-feu sur Debian
      ansible.builtin.apt:
        name: ufw
        state: present
      when: ansible_os_family == "Debian"
```

`when:` est une expression Jinja2 **sans** accolades. On combine avec `and`, `or`, ou une liste (toutes vraies). Usages fréquents : selon l'OS, selon un groupe (`"web" in group_names`), selon le résultat d'une tâche précédente.

!!Des accolades dans when transforment la condition en chaîne de caractères : elle peut être toujours vraie!!

## Enregistrer un résultat

```yaml
    - name: Tester l'application
      ansible.builtin.uri:
        url: "http://localhost:{{ nginx_port }}/health"
        status_code: 200
      register: health
      retries: 5
      delay: 3
      until: health.status == 200
```

`register` garde le résultat dans une variable ; `until`, `retries` et `delay` attendent qu'un service soit prêt. `ansible.builtin.debug: var=health` affiche son contenu.

## Labo réel

Testez un template sur votre poste, sans serveur :

```bash
ansible localhost -c local -m ansible.builtin.template \
  -a "src=templates/nginx.conf.j2 dest=/tmp/nginx.test.conf" \
  -e @group_vars/web.yml
cat /tmp/nginx.test.conf
```

**À retenir :** `template` avec `validate` et `%s` ; Jinja2 `{{ }}`, `{% for %}`, filtres et `default` ; en-tête « Géré par Ansible » ; `loop` et `item`, ou une liste passée au module ; `when` sans accolades ; `register`, `until`, `retries`.
