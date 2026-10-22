#!/usr/bin/env bash
# Contrôle du boss auto1 : lance l12/quotidien.py de l apprenant sur des données jetables. cwd = racine de l espace de travail.
timeout 50 python3 -B "$LESSON_DIR/_boss.py" 3
rc=$?
[ $rc -eq 124 ] && echo "ECHEC : le contrôle a dépassé 50 s (quotidien.py trop lent ?)."
exit $rc
