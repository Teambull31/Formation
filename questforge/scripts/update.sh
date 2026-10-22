#!/usr/bin/env bash
# Met à jour un QuestForge déployé avec docker compose : récupère le code, reconstruit, relance, teste.
#   scripts/update.sh            (profil https : COMPOSE_PROFILES=https scripts/update.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "Fichier .env introuvable : copiez .env.example en .env et renseignez QUESTFORGE_PASSWORD." >&2; exit 1; }

git pull --ff-only
docker compose up -d --build

# Mot de passe lu dans .env, sans jamais l'afficher.
PASSWORD="$(grep -E '^QUESTFORGE_PASSWORD=' .env | head -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"
HOST_PORT="$(grep -E '^HOST_PORT=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
URL="${QUESTFORGE_URL:-http://127.0.0.1:${HOST_PORT:-3000}}"

scripts/smoke.sh "$URL" "$PASSWORD"
docker image prune -f >/dev/null
echo "Mise à jour terminée."
