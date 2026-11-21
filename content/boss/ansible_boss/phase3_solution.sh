#!/usr/bin/env bash
# Solution de référence, phase 3 : le dossier de départ et la solution du TP an6, dans ansibleboss/.
set -euo pipefail
mkdir -p ansibleboss
cd ansibleboss
cp -r "$LESSON_DIR/../../modules/ansible/lessons/an6.tp/seed/." .
bash "$LESSON_DIR/../../modules/ansible/lessons/an6.tp/solution.sh"
