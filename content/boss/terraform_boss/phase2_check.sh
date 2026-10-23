#!/usr/bin/env bash
# Contrôle du boss terraform, phase 2 : analyse statique en lecture seule de tfboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 2 revérifie aussi les phases précédentes. Aucun réseau, aucun binaire terraform.
exec python3 -I -B "$LESSON_DIR/../../modules/terraform/lessons/_hcl_check.py" boss2 tfboss
