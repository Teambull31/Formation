#!/usr/bin/env bash
# Solution de référence, phase 5 : le corrigé du TP tf5, dans tfboss-module/.
set -euo pipefail
TP="$LESSON_DIR/../../modules/terraform/lessons/tf5.tp"
mkdir -p tfboss-module
cp -r "$TP/seed/." tfboss-module/
cd tfboss-module
bash "$TP/solution.sh"
