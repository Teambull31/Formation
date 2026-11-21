#!/usr/bin/env bash
# Contrôle du boss terraform, phase 6 : analyse statique en lecture seule (cwd = racine de l'espace de travail).
# Cumulatif : revérifie tfboss/ (phases 1 à 3) et les phases avancées précédentes. Aucun réseau, aucun binaire terraform.
set -e
H="$LESSON_DIR/../../modules/terraform/lessons/_hcl_check.py"
python3 -I -B "$H" boss3 tfboss
python3 -I -B "$H" tf4 tfboss-boucles
python3 -I -B "$H" tf5 tfboss-module
exec python3 -I -B "$H" tf6 tfboss-ci
