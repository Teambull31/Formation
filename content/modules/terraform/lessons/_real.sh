#!/usr/bin/env bash
# Labo réel du module Terraform : terraform init (sans backend) puis validate et fmt (cwd = dossier du TP).
# init télécharge les providers (réseau) et crée .terraform/ dans le dossier du TP. Code 3 : terraform absent.
set -u
compgen -G "*.tf" >/dev/null || { echo "ECHEC : aucun fichier .tf dans le dossier"; exit 1; }
if ! command -v terraform >/dev/null; then
  echo "OUTIL ABSENT : terraform. Installez-le : https://developer.hashicorp.com/terraform/install"
  exit 3
fi
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}" TF_IN_AUTOMATION=1
mkdir -p "$TF_PLUGIN_CACHE_DIR"
echo "\$ terraform init -backend=false"
log=$(terraform init -backend=false -input=false -no-color 2>&1) || { echo "$log"; exit 1; }
echo "\$ terraform validate"
terraform validate -no-color || exit 1
echo "\$ terraform fmt -check -recursive"
terraform fmt -check -recursive -no-color || echo "(fmt) mise en forme à revoir : lancez terraform fmt -recursive"
echo "OK : terraform valide la configuration. Essayez : terraform plan"
