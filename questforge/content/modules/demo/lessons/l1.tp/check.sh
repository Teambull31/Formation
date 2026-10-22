#!/usr/bin/env bash
set -e
if [ ! -f config.json ]; then
  echo "Erreur: config.json introuvable" >&2
  exit 1
fi
grep -q "demo" config.json || { echo "Erreur: 'demo' non trouvé dans config.json" >&2; exit 1; }
echo "Vérification réussie !"
exit 0
