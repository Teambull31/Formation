#!/usr/bin/env bash
# Contrôle du TP es7 : compile main.cpp contre le faux ESP-IDF et vérifie les deux exécutions (cwd = dossier du TP).
exec python3 -I -B "$LESSON_DIR/../../../../esp/esp_check.py" es7-tp
