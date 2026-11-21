#!/usr/bin/env bash
# Contrôle du TP dk4 : lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_docker_check.py" dk4
