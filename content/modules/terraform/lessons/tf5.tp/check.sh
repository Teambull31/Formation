#!/usr/bin/env bash
# Contrôle du TP tf5 : analyse statique en lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_hcl_check.py" tf5
