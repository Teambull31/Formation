#!/usr/bin/env bash
# Labo réel du module Kubernetes : kubeconform, ou kubectl contre un cluster (kind) s'il répond (cwd = dossier du TP).
# Code 3 : aucun outil utilisable.
set -u
mapfile -t files < <(find . -name '*.y*ml' -not -name diagnostic.yaml -not -name kustomization.yaml -not -path '*/incidents/*' -not -path './.*' | sort)
[ ${#files[@]} -gt 0 ] || { echo "ECHEC : aucun manifeste YAML dans le dossier"; exit 1; }
if command -v kubeconform >/dev/null; then
  echo "\$ kubeconform -strict -summary ${files[*]}"
  kubeconform -strict -summary -ignore-missing-schemas "${files[@]}" || exit 1
elif command -v kubectl >/dev/null && kubectl version --request-timeout=3s >/dev/null 2>&1; then
  for f in "${files[@]}"; do
    echo "\$ kubectl apply --dry-run=server -f $f"
    kubectl apply --dry-run=server -f "$f" || exit 1
  done
else
  echo "OUTIL ABSENT : ni kubeconform, ni kubectl relié à un cluster."
  echo "Le plus simple : installez kind et kubectl, puis : kind create cluster --name formation"
  exit 3
fi
if [ -f kustomization.yaml ] && command -v kubectl >/dev/null; then
  echo "\$ kubectl kustomize ."; kubectl kustomize . >/dev/null || exit 1
fi
echo "OK : les manifestes sont acceptés."
