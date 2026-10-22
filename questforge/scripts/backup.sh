#!/usr/bin/env bash
# Sauvegarde la progression (base SQLite + dossier de travail des TP) dans une archive datée.
#   scripts/backup.sh [dossier-de-destination]     (par défaut : ./backups)
# Restaurer : docker compose exec -T questforge tar xzf - -C /data < backups/questforge-AAAA-MM-JJ.tgz
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:-backups}"
mkdir -p "$DEST"
FILE="$DEST/questforge-$(date +%F-%H%M).tgz"
docker compose exec -T questforge tar czf - -C /data . > "$FILE"
echo "Sauvegarde écrite : $FILE ($(du -h "$FILE" | cut -f1))"
