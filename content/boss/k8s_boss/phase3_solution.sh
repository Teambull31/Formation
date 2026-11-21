#!/usr/bin/env bash
# Solution de référence, phase 3 : la base et la solution du TP k7, dans k8sboss/.
set -euo pipefail
mkdir -p k8sboss
cd k8sboss
cp -r "$LESSON_DIR/../../modules/k8s/lessons/k7.tp/seed/." .
bash "$LESSON_DIR/../../modules/k8s/lessons/k7.tp/solution.sh"
