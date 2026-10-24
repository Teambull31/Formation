#!/usr/bin/env bash
# Contrôle du TP sc3 : lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_secu_check.py" sc3
