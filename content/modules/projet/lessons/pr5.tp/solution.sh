#!/usr/bin/env bash
# Solution de référence, étape 5 du projet : la configuration Ansible et le README.
set -euo pipefail
LESSON_DIR="$LESSON_DIR/../pr4.tp" bash "$LESSON_DIR/../pr4.tp/solution.sh"
mkdir -p ansible/templates
cat > ansible/inventory.ini <<'INI'
[web]
web-1 ansible_host=10.0.1.11
web-2 ansible_host=10.0.1.12

[web:vars]
ansible_user=deploy
INI
cat > ansible/templates/commandes.service.j2 <<'J2'
# Géré par Ansible : toute modification à la main sera écrasée
[Service]
ExecStart=/usr/bin/docker run --rm --name commandes -p 127.0.0.1:8000:8000 {{ image }}
Restart=always
J2
cat > ansible/site.yml <<'YML'
- name: Serveurs web
  hosts: web
  become: true
  serial: 1
  max_fail_percentage: 0
  vars:
    image: "ghcr.io/moncompte/commandes:3f2a9c1"
  tasks:
    - name: Installer Docker
      ansible.builtin.apt:
        name: docker.io
        state: present
        update_cache: true
    - name: Déposer le service commandes
      ansible.builtin.template:
        src: templates/commandes.service.j2
        dest: /etc/systemd/system/commandes.service
        owner: root
        group: root
        mode: "0644"
      notify: Redémarrer commandes
    - name: Démarrer commandes
      ansible.builtin.systemd_service:
        name: commandes
        state: started
        enabled: true
        daemon_reload: true
  handlers:
    - name: Redémarrer commandes
      ansible.builtin.systemd_service:
        name: commandes
        state: restarted
        daemon_reload: true
YML
cat > README.md <<'MD'
# Commandes : de l'application à la production

Une petite API de commandes (Python, bibliothèque standard) livrée comme en entreprise : tests et image publiés par la CI, déploiement Kubernetes, infrastructure décrite en Terraform et serveurs configurés par Ansible.

## Architecture

- `app/` : l'API (`/healthz`, `/total`) et ses tests.
- `.github/workflows/ci.yml` : tests sur chaque pull request, image publiée sur ghcr.io depuis main, étiquetée par commit.
- `Dockerfile` : build multi-stage, utilisateur non-root, HEALTHCHECK.
- `k8s/` : Deployment durci, Service, Kustomization.
- `infra/` : Terraform, state distant chiffré et verrouillé, environnement validé.
- `ansible/` : déploiement progressif sur les serveurs web, un à la fois.

## Démarrer en local

```bash
pip install -r requirements.txt && pytest -q
python -m app.main   # puis curl http://127.0.0.1:8000/healthz
```

## Déployer

1. Une pull request lance les tests ; la fusion dans main publie l'image.
2. `kubectl apply -k k8s/` déploie sur le cluster.
3. `terraform -chdir=infra plan` puis `apply` pour l'infrastructure.
4. `ansible-playbook -i ansible/inventory.ini ansible/site.yml` pour les serveurs hors cluster.
MD
