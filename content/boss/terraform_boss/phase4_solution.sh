#!/usr/bin/env bash
# Solution de référence, phase 4 : le corrigé du TP tf4, dans tfboss-boucles/.
set -euo pipefail
TP="$LESSON_DIR/../../modules/terraform/lessons/tf4.tp"
mkdir -p tfboss-boucles
cp -r "$TP/seed/." tfboss-boucles/
cd tfboss-boucles
bash "$TP/solution.sh"
