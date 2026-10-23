#!/usr/bin/env bash
# Mise à jour : récupère le code, reconstruit l'image, redémarre, puis lance le test de fumée.
#   scripts/update.sh [url]      (défaut : http://127.0.0.1:${HOST_PORT:-8000})
# Lit FORMATION_PASSWORD dans l'environnement ou dans .env (jamais affiché).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

URL="${1:-http://127.0.0.1:${HOST_PORT:-8000}}"
PROFILE=()
[ -n "${DOMAIN:-}" ] && PROFILE=(--profile https)

git pull --ff-only
docker compose "${PROFILE[@]}" up -d --build
FORMATION_PASSWORD="${FORMATION_PASSWORD:-}" scripts/smoke.sh "$URL"
