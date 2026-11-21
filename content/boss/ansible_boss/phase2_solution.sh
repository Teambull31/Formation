#!/usr/bin/env bash
# Solution de référence, phase 2 : le dossier de départ et la solution du TP an5, dans ansibleboss/.
set -euo pipefail
mkdir -p ansibleboss
cd ansibleboss
cp -r "$LESSON_DIR/../../modules/ansible/lessons/an5.tp/seed/." .
bash "$LESSON_DIR/../../modules/ansible/lessons/an5.tp/solution.sh"
