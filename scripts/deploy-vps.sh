#!/usr/bin/env bash
# Déploie sur le VPS (services systemd formation et formation-tp, pas Docker). À lancer depuis le PC :
#   scripts/deploy-vps.sh [hôte_ssh]      (défaut : vps)
# Prérequis : commit poussé sur origin/main. Les mp3 de content/podcast (hors git) sont envoyés par rsync.
set -euo pipefail
HOST="${1:-vps}"
cd "$(dirname "$0")/.."

[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Modifications non commitées : commit + push d'abord" >&2; exit 1; }
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "HEAD différent de origin/main : push d'abord" >&2; exit 1; }

rsync -a content/podcast/*.mp3 "$HOST:Formation/content/podcast/" 2>/dev/null || echo "(aucun mp3 de podcast à envoyer)"

# uv est dans ~/.local/bin, absent du PATH d'un shell SSH non interactif
ssh "$HOST" 'set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd ~/Formation
git pull -q --ff-only
(cd backend && uv sync -q)
(cd frontend && npm ci --silent && npm run build --silent >/dev/null)
sudo systemctl restart formation formation-tp
sleep 3
systemctl is-active formation formation-tp
curl -fsS -o /dev/null http://127.0.0.1:8001/api/lessons && echo "test de fumée : OK"
git log --oneline -1
# préchauffe en tâche de fond les audios des leçons modifiées (sinon la première écoute attend la synthèse)
# (toutes les sorties redirigées, sinon la session SSH attend la fin du préchauffage)
pkill -f "app[.]warm_audio" || true  # [.] : le motif ne se reconnaît pas dans cette commande
cd backend
nohup uv run python -m app.warm_audio ../content >~/warm_audio.log 2>&1 </dev/null &
echo "préchauffage audio lancé (journal : ~/warm_audio.log)"'
