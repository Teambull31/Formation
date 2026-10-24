#!/usr/bin/env bash
# Contrôle du boss docker, phase 1 : analyse statique en lecture seule de dockerboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 1 revérifie aussi les phases précédentes. Aucun démon Docker, aucun réseau.
exec python3 -I -B "$LESSON_DIR/../../modules/docker/lessons/_docker_check.py" boss1 dockerboss
