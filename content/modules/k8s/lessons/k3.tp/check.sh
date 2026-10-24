#!/usr/bin/env bash
# Contrôle du TP k3 : lecture seule du dossier courant (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../_k8s_check.py" k3
