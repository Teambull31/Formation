#!/usr/bin/env bash
# Sauvegarde horodatée : base SQLite (copie cohérente via l'API backup) + archive du dossier de travail.
#   scripts/backup.sh [dossier-de-sortie]            installation native (FORMATION_DB / FORMATION_WORKSPACE, défaut ~/.formation)
#   BACKUP_DOCKER=1 scripts/backup.sh [dossier]      conteneur « formation » lancé par docker compose
set -euo pipefail

OUT="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

PYBACKUP='import sqlite3, sys
src = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()'

if [ "${BACKUP_DOCKER:-0}" = 1 ]; then
  docker compose exec -T formation python -c "$PYBACKUP" /data/formation.db /tmp/backup.db
  docker compose exec -T formation cat /tmp/backup.db >"$OUT/formation-$STAMP.db"
  docker compose exec -T formation rm -f /tmp/backup.db
  docker compose exec -T formation tar -C /data -czf - workspace >"$OUT/workspace-$STAMP.tgz"
else
  DB="${FORMATION_DB:-$HOME/.formation/formation.db}"
  WS="${FORMATION_WORKSPACE:-$HOME/.formation/workspace}"
  [ -f "$DB" ] || { echo "Base introuvable : $DB" >&2; exit 1; }
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB" ".backup '$OUT/formation-$STAMP.db'"
  else
    python3 -c "$PYBACKUP" "$DB" "$OUT/formation-$STAMP.db"
  fi
  if [ -d "$WS" ]; then
    tar -C "$(dirname "$WS")" -czf "$OUT/workspace-$STAMP.tgz" "$(basename "$WS")"
  fi
fi

echo "Sauvegarde écrite dans $OUT (formation-$STAMP.db, workspace-$STAMP.tgz)"
