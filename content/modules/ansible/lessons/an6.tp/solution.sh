#!/usr/bin/env bash
# Solution de référence du TP an6.
set -euo pipefail
cat > deploy.yml <<'EOF'
- name: Déployer l'application
  hosts: web
  become: true
  serial: 1
  max_fail_percentage: 0
  pre_tasks:
    - name: Retirer du répartiteur
      ansible.builtin.uri:
        url: "http://lb.internal/api/drain/{{ inventory_hostname }}"
        method: POST
      delegate_to: localhost
      become: false
  roles:
    - role: app
  post_tasks:
    - name: Attendre que l'application réponde
      ansible.builtin.uri:
        url: "http://{{ ansible_host }}:8000/health"
      register: health
      until: health.status == 200
      retries: 10
      delay: 3
    - name: Remettre dans le répartiteur
      ansible.builtin.uri:
        url: "http://lb.internal/api/enable/{{ inventory_hostname }}"
        method: POST
      delegate_to: localhost
      become: false
EOF
mkdir -p .github/workflows
cat > .github/workflows/ansible.yml <<'EOF'
name: Ansible
on:
  pull_request:
permissions:
  contents: read
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: pip install ansible-core==2.17.5 ansible-lint==24.9.2
      - run: ansible-lint
      - run: ansible-playbook -i inventory.ini deploy.yml --syntax-check
EOF
