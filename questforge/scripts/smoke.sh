#!/usr/bin/env bash
# Test de fumée d'un QuestForge en marche.
#   scripts/smoke.sh http://localhost:3000 [mot-de-passe]
#   QUESTFORGE_PASSWORD=... scripts/smoke.sh https://formation.exemple.fr
# Code de sortie : 0 si tout passe, 1 sinon. Le mot de passe n'apparaît jamais dans la liste des processus.
set -u
BASE="${1:?Usage: $0 <url> [mot-de-passe]}"
BASE="${BASE%/}"
PASSWORD="${2:-${QUESTFORGE_PASSWORD:-}}"
FAILS=0

req() { # req <méthode> <chemin> [authentifié=1] -> corps, puis code HTTP sur la dernière ligne
  local method="$1" path="$2" authed="${3:-1}"
  if [ -n "$PASSWORD" ] && [ "$authed" = 1 ]; then
    curl -sS --max-time 20 -X "$method" -K <(printf 'user = "questforge:%s"\n' "$PASSWORD") -w '\n%{http_code}' "$BASE$path"
  else
    curl -sS --max-time 20 -X "$method" -w '\n%{http_code}' "$BASE$path"
  fi
}

check() { # check <description> <attendu: code> <méthode> <chemin> <authentifié> [motif attendu dans le corps]
  local label="$1" want="$2" method="$3" path="$4" authed="$5" pattern="${6:-}"
  local out code body
  out="$(req "$method" "$path" "$authed" 2>&1)" || { echo "ÉCHEC  $label : $out"; FAILS=$((FAILS + 1)); return; }
  code="${out##*$'\n'}"; body="${out%$'\n'*}"
  if [ "$code" != "$want" ]; then
    echo "ÉCHEC  $label : HTTP $code (attendu $want)"; FAILS=$((FAILS + 1)); return
  fi
  if [ -n "$pattern" ] && ! grep -q -- "$pattern" <<<"$body"; then
    echo "ÉCHEC  $label : la réponse ne contient pas « $pattern »"; FAILS=$((FAILS + 1)); return
  fi
  echo "ok     $label"
}

# Attend le démarrage (jusqu'à 90 s) : le backend Python met quelques secondes à répondre.
for _ in $(seq 1 45); do
  curl -s -o /dev/null --max-time 3 -f "$BASE/healthz" && break
  sleep 2
done

check "sonde de santé"                       200 GET  /healthz 0 ok
if [ -n "$PASSWORD" ]; then
  check "API refusée sans mot de passe"      401 GET  /api/quest 0
  check "action sensible refusée sans mot de passe" 401 POST /api/tp/tf1_tp/check 0
fi
check "page d'accueil"                       200 GET  / 1 QuestForge
check "quête du jour"                        200 GET  /api/quest 1 '"steps"'
check "parcours dont Terraform"              200 GET  /api/modules 1 '"terraform"'
check "boss Terraform"                       200 GET  /api/bosses 1 boss_terraform
check "vérification d'un TP (script réel)"   200 POST /api/tp/tf1_tp/check 1 '"passed"'

if [ "$FAILS" -eq 0 ]; then echo "Tout est bon."; else echo "$FAILS vérification(s) en échec."; fi
[ "$FAILS" -eq 0 ]
