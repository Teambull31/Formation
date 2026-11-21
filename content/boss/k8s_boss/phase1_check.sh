#!/usr/bin/env bash
# Contrôle du boss Kubernetes, phase 1 : analyse statique en lecture seule de k8sboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 1 revérifie aussi les phases précédentes. Aucun cluster, aucun réseau.
exec python3 -I -B "$LESSON_DIR/../../modules/k8s/lessons/_k8s_check.py" boss1 k8sboss
