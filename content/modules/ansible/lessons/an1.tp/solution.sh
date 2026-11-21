#!/usr/bin/env bash
# Solution de référence du TP an1.
set -euo pipefail
cat > inventory.ini <<'EOF'
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
EOF
cat > site.yml <<'EOF'
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
EOF
