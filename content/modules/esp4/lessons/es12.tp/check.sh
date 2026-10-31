#!/usr/bin/env bash
# Contrôle du TP es12 : compile main.cpp contre le faux ESP-IDF et vérifie les six exécutions (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../../../../esp/esp_check.py" es12-tp
