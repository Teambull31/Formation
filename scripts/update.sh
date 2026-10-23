#!/usr/bin/env bash
# Mise à jour : récupère le code, reconstruit l'image, redémarre, puis lance le test de fumée.
#   scripts/update.sh [url]      (défaut : http://127.0.0.1:${HOST_PORT:-8000})
# Lit FORMATION_PASSWORD dans l'environnement ou dans .env (jamais affiché).
set -euo pipefail

cd "$(dirname "$0")/.."

# .env n'est jamais exécuté comme du shell : on lit seulement KEY=VALUE, pour les clés utiles.
env_get() { # env_get <clé> : dernière valeur dans .env, guillemets externes retirés
  [ -f .env ] || return 0
  local v
  v="$(grep -E "^$1=" .env | tail -n1)" || true
  v="${v#"$1="}"
  case "$v" in
    \"*\") v="${v#\"}"; v="${v%\"}" ;;
    \'*\') v="${v#\'}"; v="${v%\'}" ;;
  esac
  printf '%s' "$v"
}
FORMATION_PASSWORD="${FORMATION_PASSWORD:-$(env_get FORMATION_PASSWORD)}"
DOMAIN="${DOMAIN:-$(env_get DOMAIN)}"
HOST_PORT="${HOST_PORT:-$(env_get HOST_PORT)}"

URL="${1:-http://127.0.0.1:${HOST_PORT:-8000}}"
PROFILE=()
[ -n "${DOMAIN:-}" ] && PROFILE=(--profile https)

git pull --ff-only
docker compose "${PROFILE[@]}" up -d --build
SMOKE_PASSWORD="$FORMATION_PASSWORD" scripts/smoke.sh "$URL"
