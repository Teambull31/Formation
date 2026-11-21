#!/usr/bin/env bash
# Solution de référence du TP an4.
set -euo pipefail
mkdir -p roles/nginx/templates
mv templates/nginx.conf.j2 roles/nginx/templates/nginx.conf.j2
rmdir templates
mkdir -p roles/nginx/tasks
cat > roles/nginx/tasks/main.yml <<'EOF'
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
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: "0644"
    validate: nginx -t -c %s
  notify: Recharger nginx
EOF
mkdir -p roles/nginx/handlers
cat > roles/nginx/handlers/main.yml <<'EOF'
- name: Recharger nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded
EOF
mkdir -p roles/nginx/defaults
cat > roles/nginx/defaults/main.yml <<'EOF'
nginx_port: 80
nginx_sites: []
EOF
mkdir -p roles/nginx/meta
cat > roles/nginx/meta/main.yml <<'EOF'
galaxy_info:
  author: formation
  description: Installe et configure nginx
  license: MIT
  min_ansible_version: "2.15"
dependencies: []
EOF
cat > site.yml <<'EOF'
- name: Serveurs web
  hosts: web
  become: true
  roles:
    - role: nginx
EOF
cat > requirements.yml <<'EOF'
collections:
  - name: community.general
    version: "9.4.0"
  - name: ansible.posix
    version: "1.6.2"
EOF
