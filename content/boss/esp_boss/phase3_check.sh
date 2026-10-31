#!/usr/bin/env bash
# Contrôle du boss ESP, phase 3 : la livraison : OTA valide ou corrompue, coupure de courant, certificat invalide, retour arrière (leçons es11 et es12).
# cwd = racine de l'espace de travail ; le programme est espboss/main.cpp. Compile contre le faux ESP-IDF et juge les exécutions simulées
# (cumulatif : la phase 3 revérifie aussi les phases précédentes). Aucun réseau, aucune carte.
cd espboss 2>/dev/null || { echo "ECHEC : le dossier espboss/ n'existe pas : le boss se travaille dans espboss/main.cpp, à la racine de l'espace de travail"; exit 1; }
exec python3 -I -B "$LESSON_DIR/../../esp/esp_check.py" esp_boss_p3
