#!/usr/bin/env bash
# Labo réel du module CI/CD : actionlint sur les workflows du TP (cwd = dossier du TP). Code 3 : outil absent.
set -u
shopt -s nullglob
files=(.github/workflows/*.yml .github/workflows/*.yaml)
[ ${#files[@]} -gt 0 ] || { echo "ECHEC : aucun workflow dans .github/workflows/"; exit 1; }
if ! command -v actionlint >/dev/null; then
  echo "OUTIL ABSENT : actionlint."
  echo "Installez le binaire dans ~/.local/bin : https://github.com/rhysd/actionlint/releases"
  exit 3
fi
echo "\$ actionlint ${files[*]}"
actionlint "${files[@]}" || exit 1
echo "OK : actionlint ne signale rien sur ${#files[@]} workflow(s)."
