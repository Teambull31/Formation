#!/usr/bin/env bash
# Labo réel du module Ansible : --syntax-check sur chaque playbook, puis ansible-lint s'il est installé (cwd = dossier du TP).
# Aucune tâche n'est exécutée. Code 3 : ansible absent.
set -u
if ! command -v ansible-playbook >/dev/null; then
  echo "OUTIL ABSENT : ansible. Installez-le : pip install --user ansible-core"
  exit 3
fi
inv=localhost,
[ -f inventory.ini ] && inv=inventory.ini
mapfile -t books < <(grep -l -E '^\s*hosts:' ./*.yml 2>/dev/null)
[ ${#books[@]} -gt 0 ] || { echo "ECHEC : aucun playbook (fichier .yml avec hosts:) à la racine du dossier"; exit 1; }
for b in "${books[@]}"; do
  echo "\$ ansible-playbook -i $inv $b --syntax-check"
  ANSIBLE_NOCOLOR=1 ansible-playbook -i "$inv" "$b" --syntax-check || exit 1
done
[ -f inventory.ini ] && { echo "\$ ansible-inventory -i inventory.ini --graph"; ansible-inventory -i inventory.ini --graph || exit 1; }
if command -v ansible-lint >/dev/null; then
  echo "\$ ansible-lint (informatif)"; ansible-lint "${books[@]}" || echo "(lint) remarques ci-dessus : à corriger si possible"
fi
echo "OK : Ansible accepte les playbooks."
