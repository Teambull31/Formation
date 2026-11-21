#!/usr/bin/env bash
# Labo réel du projet fil rouge : chaque outil installé vérifie sa partie (cwd = dossier du projet). Code 3 : aucun outil.
set -u
ran=0
step() { echo; echo "\$ $*"; }
if [ -d app ] && python3 -c "import pytest" 2>/dev/null; then
  step python3 -m pytest -q app; python3 -m pytest -q app || exit 1; ran=1
fi
if [ -d .github/workflows ] && command -v actionlint >/dev/null; then
  step actionlint; actionlint || exit 1; ran=1
fi
if [ -f Dockerfile ] && command -v hadolint >/dev/null; then
  step hadolint Dockerfile; hadolint Dockerfile || exit 1; ran=1
fi
if [ -d k8s ] && command -v kubectl >/dev/null; then
  step kubectl kustomize k8s; kubectl kustomize k8s >/dev/null || exit 1; ran=1
fi
if [ -d infra ] && command -v terraform >/dev/null; then
  export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}" TF_IN_AUTOMATION=1
  mkdir -p "$TF_PLUGIN_CACHE_DIR"
  step terraform -chdir=infra validate
  log=$(terraform -chdir=infra init -backend=false -input=false -no-color 2>&1) || { echo "$log"; exit 1; }
  terraform -chdir=infra validate -no-color || exit 1; ran=1
fi
if [ -f ansible/site.yml ] && command -v ansible-playbook >/dev/null; then
  step ansible-playbook --syntax-check ansible/site.yml
  (cd ansible && ANSIBLE_NOCOLOR=1 ansible-playbook -i inventory.ini site.yml --syntax-check) || exit 1; ran=1
fi
if [ "$ran" = 0 ]; then
  echo "OUTIL ABSENT : aucun des outils du projet (pytest, actionlint, hadolint, kubectl, terraform, ansible) n'est installé."
  exit 3
fi
echo; echo "OK : chaque outil installé accepte sa partie du projet."
