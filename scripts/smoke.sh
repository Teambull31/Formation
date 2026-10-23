#!/usr/bin/env bash
# Test de fumée d'une instance en marche.
#   scripts/smoke.sh http://127.0.0.1:8000 [mot-de-passe]
#   FORMATION_PASSWORD=... scripts/smoke.sh https://formation.exemple.fr
# Le mot de passe n'apparaît ni dans les arguments des processus ni dans la sortie.
# Le contrôle « action sensible refusée » force un Host non autorisé : il attend 403, avec ou sans FORMATION_REMOTE_EXEC.
# Il n'est pertinent que contre l'URL directe de l'appli (derrière un proxy à nom de domaine, le Host forcé n'atteint pas l'appli).
set -euo pipefail

BASE="${1:?Usage: $0 <url> [mot-de-passe]}"
BASE="${BASE%/}"
PASSWORD="${2:-${FORMATION_PASSWORD:-}}"
FAILS=0

# code_http <méthode> <chemin> <authentifié 0|1> [en-tête...] -> affiche le code HTTP (000 si injoignable)
code_http() {
  local method="$1" path="$2" authed="$3"
  shift 3
  local args=(-sS -o /dev/null -w '%{http_code}' --max-time 20 -X "$method")
  local h
  for h in "$@"; do args+=(-H "$h"); done
  if [ -n "$PASSWORD" ] && [ "$authed" = 1 ]; then
    curl "${args[@]}" -K <(printf 'user = "smoke:%s"\n' "$PASSWORD") "$BASE$path" 2>/dev/null || true
  else
    curl "${args[@]}" "$BASE$path" 2>/dev/null || true
  fi
}

check() { # check <description> <code attendu> <méthode> <chemin> <authentifié> [en-tête...]
  local label="$1" want="$2" got
  shift 2
  got="$(code_http "$@")"
  if [ "$got" = "$want" ]; then
    echo "ok     $label"
  else
    echo "ECHEC  $label : HTTP $got (attendu $want)"
    FAILS=$((FAILS + 1))
  fi
}

# Attente du démarrage (90 s max) : 200 ou 401 = le serveur répond.
for _ in $(seq 1 45); do
  c="$(code_http GET /manifest.webmanifest 0)"
  [ "$c" = 200 ] || [ "$c" = 401 ] && break
  sleep 2
done

if [ -n "$PASSWORD" ]; then
  check "API refusée sans mot de passe" 401 GET /api/quest 0
fi
check "page d'accueil" 200 GET / 1
check "manifest PWA" 200 GET /manifest.webmanifest 1
check "quête du jour" 200 GET /api/quest 1
check "action sensible refusée depuis un Host non autorisé" 403 POST /api/tp/smoke/start 1 'Host: smoke.invalid'

if [ "$FAILS" -eq 0 ]; then echo "Tout est bon."; else echo "$FAILS vérification(s) en échec."; fi
[ "$FAILS" -eq 0 ]
