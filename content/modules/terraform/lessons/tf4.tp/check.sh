#!/usr/bin/env bash
# Contrôle du TP tf4 : analyse statique en lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_hcl_check.py" tf4
