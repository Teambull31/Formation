#!/usr/bin/env bash
# Contrôle du TP dk3 : analyse statique en lecture seule du dossier courant (cwd = dossier du TP).
# Aucun démon Docker, aucun réseau ; python sans site ni dossier courant (-I -B).
exec python3 -I -B "$LESSON_DIR/../_docker_check.py" dk3
