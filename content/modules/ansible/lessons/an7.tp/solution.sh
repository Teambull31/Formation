#!/usr/bin/env bash
# Solution de référence du TP an7.
set -euo pipefail
cat > diagnostic.yaml <<'DIAG'
compression: idempotence
site: handler
db1: inventaire
pare-feu: condition
comptes: fuite
DIAG
sed -i 's/^db1 ansible_host=10.0.2.12$/db1 ansible_host=10.0.2.21/' inventory.ini
cat > site.yml <<'YML'
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Activer la compression
      ansible.builtin.copy:
        content: "gzip on;\n"
        dest: /etc/nginx/conf.d/gzip.conf
        owner: root
        group: root
        mode: "0644"
      notify: Recharger nginx
    - name: Déposer la configuration du site
      ansible.builtin.template:
        src: templates/site.conf.j2
        dest: /etc/nginx/conf.d/site.conf
        owner: root
        group: root
        mode: "0644"
      notify: Recharger nginx
    - name: Ouvrir le port 443
      community.general.ufw:
        rule: allow
        port: "443"
      when: ansible_os_family == "Debian"
  handlers:
    - name: Recharger nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded

- name: Base de données
  hosts: db
  become: true
  tasks:
    - name: Créer le compte applicatif
      community.postgresql.postgresql_user:
        name: shop
        password: "{{ vault_db_password }}"
      no_log: true
YML
