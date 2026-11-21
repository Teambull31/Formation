#!/usr/bin/env bash
# Contrôle du TP an2 : analyse statique en lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_ansible_check.py" an2
