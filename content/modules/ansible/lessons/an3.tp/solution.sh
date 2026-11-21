#!/usr/bin/env bash
# Solution de référence du TP an3.
set -euo pipefail
mkdir -p templates
cat > templates/nginx.conf.j2 <<'EOF'
# Géré par Ansible : toute modification à la main sera écrasée
events {}
http {
{% for site in nginx_sites %}
  server {
    listen {{ nginx_port }};
    server_name {{ site.domain }};
    root /var/www/{{ site.name }};
  }
{% endfor %}
}
EOF
cat > site.yml <<'EOF'
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Installer les paquets de base
      ansible.builtin.apt:
        name: "{{ base_packages }}"
        state: present
        update_cache: true
      when: ansible_os_family == "Debian"
    - name: Créer les comptes administrateurs
      ansible.builtin.user:
        name: "{{ item.name }}"
        groups: "{{ item.groups }}"
        shell: /bin/bash
      loop: "{{ admins }}"
    - name: Configurer nginx
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: "0644"
        validate: nginx -t -c %s
      notify: Recharger nginx
  handlers:
    - name: Recharger nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
EOF
