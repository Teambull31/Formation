#!/usr/bin/env bash
# Solution de référence, phase 1 : le dossier de départ et la solution du TP an4, dans ansibleboss/.
set -euo pipefail
mkdir -p ansibleboss
cd ansibleboss
cp -r "$LESSON_DIR/../../modules/ansible/lessons/an4.tp/seed/." .
bash "$LESSON_DIR/../../modules/ansible/lessons/an4.tp/solution.sh"
