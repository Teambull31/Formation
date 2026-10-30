#!/usr/bin/env bash
# Contrôle du TP es10 : compile main.cpp contre le faux ESP-IDF et vérifie les trois exécutions (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../../../../esp/esp_check.py" es10-tp
