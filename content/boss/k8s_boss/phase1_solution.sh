#!/usr/bin/env bash
# Solution de référence, phase 1 : la solution du TP k2, dans k8sboss/.
set -euo pipefail
mkdir -p k8sboss
cd k8sboss
bash "$LESSON_DIR/../../modules/k8s/lessons/k2.tp/solution.sh"
