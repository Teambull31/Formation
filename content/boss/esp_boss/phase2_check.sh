#!/usr/bin/env bash
# Contrôle du boss ESP, phase 2 : la liaison : Wi-Fi, MQTT sur TLS, reprise après coupure, consigne en NVS (leçons es10 et es9).
# cwd = racine de l'espace de travail ; le programme est espboss/main.cpp. Compile contre le faux ESP-IDF et juge les exécutions simulées
# (cumulatif : la phase 2 revérifie aussi les phases précédentes). Aucun réseau, aucune carte.
racine=$(pwd -P)
cd -P espboss 2>/dev/null || { echo "ECHEC : le dossier espboss/ n'existe pas : le boss se travaille dans espboss/main.cpp, à la racine de l'espace de travail"; exit 1; }
case "$(pwd -P)/" in
  "$racine"/*) ;;
  *) echo "ECHEC : espboss/ pointe hors de l'espace de travail (lien symbolique) : le boss se travaille dans un vrai dossier espboss/"; exit 1 ;;
esac
exec python3 -I -B "$LESSON_DIR/../../esp/esp_check.py" esp_boss_p2
