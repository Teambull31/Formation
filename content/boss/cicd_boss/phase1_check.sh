#!/usr/bin/env bash
# Contrôle du boss CI/CD, phase 1 : analyse statique en lecture seule de ciboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 1 revérifie aussi les phases précédentes. Aucun réseau, aucun appel à GitHub.
exec python3 -I -B "$LESSON_DIR/../../modules/cicd/lessons/_cicd_check.py" boss1 ciboss
