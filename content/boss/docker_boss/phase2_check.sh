#!/usr/bin/env bash
# Contrôle du boss docker, phase 2 : analyse statique en lecture seule de dockerboss/ (cwd = racine de l'espace de travail).
# Cumulatif : la phase 2 revérifie aussi les phases précédentes. Aucun démon Docker, aucun réseau.
exec python3 -I -B "$LESSON_DIR/../../modules/docker/lessons/_docker_check.py" boss2 dockerboss
