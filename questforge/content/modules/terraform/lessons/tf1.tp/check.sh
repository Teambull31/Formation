#!/usr/bin/env bash
# Vérification du TP tf1 : l'analyse est factorisée dans ../_hcl_check.py
set -e
if ! command -v python3 >/dev/null 2>&1; then
  echo "Erreur: python3 est requis pour vérifier ce TP" >&2
  exit 1
fi
exec python3 -I "$(dirname "${BASH_SOURCE[0]}")/../_hcl_check.py" tf1
