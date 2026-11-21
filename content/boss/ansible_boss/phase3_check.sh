#!/usr/bin/env bash
# Contrôle du boss Ansible, phase 3 : analyse statique en lecture seule de ansibleboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 3 revérifie aussi les phases précédentes. Aucune connexion SSH.
exec python3 -I -B "$LESSON_DIR/../../modules/ansible/lessons/_ansible_check.py" boss3 ansibleboss
