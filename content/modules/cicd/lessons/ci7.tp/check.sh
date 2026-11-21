#!/usr/bin/env bash
# Contrôle du TP ci7 : lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_cicd_check.py" ci7
