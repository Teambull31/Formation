#!/usr/bin/env bash
# Contrôle du TP lx2 : lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_linux_check.py" lx2
