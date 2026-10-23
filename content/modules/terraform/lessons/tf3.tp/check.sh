#!/usr/bin/env bash
# Contrôle du TP tf3 : analyse statique en lecture seule du dossier courant (cwd = dossier du TP).
# Aucun réseau, aucun binaire terraform ; python sans site ni dossier courant (-I -B).
exec python3 -I -B "$LESSON_DIR/../_hcl_check.py" tf3
