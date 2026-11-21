#!/usr/bin/env bash
# Solution de référence, phase 6 : le corrigé du TP tf6, dans tfboss-ci/.
set -euo pipefail
TP="$LESSON_DIR/../../modules/terraform/lessons/tf6.tp"
mkdir -p tfboss-ci
cp -r "$TP/seed/." tfboss-ci/
cd tfboss-ci
bash "$TP/solution.sh"
