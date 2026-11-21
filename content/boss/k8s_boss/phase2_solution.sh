#!/usr/bin/env bash
# Solution de référence, phase 2 : la solution du TP k5, dans k8sboss/.
set -euo pipefail
mkdir -p k8sboss
cd k8sboss
bash "$LESSON_DIR/../../modules/k8s/lessons/k5.tp/solution.sh"
