#!/usr/bin/env bash
# Solution de référence du TP an2.
set -euo pipefail
mkdir -p group_vars
cat > group_vars/web.yml <<'EOF'
nginx_port: 8080
EOF
cat > site.yml <<'EOF'
- name: Serveurs web
  hosts: web
  become: true
  tasks:
    - name: Écrire la configuration
      ansible.builtin.copy:
        content: "server { listen {{ nginx_port }}; }\n"
        dest: /etc/nginx/conf.d/app.conf
        owner: root
        group: root
        mode: "0644"
      notify: Recharger nginx
    - name: Lire la version de nginx
      ansible.builtin.command: nginx -v
      changed_when: false
  handlers:
    - name: Recharger nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
EOF
