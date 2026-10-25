#!/usr/bin/env bash
# Contrôle du TP es4 : compile main.cpp contre le faux ESP-IDF et vérifie la trace (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../../../../esp/esp_check.py" es4-tp
