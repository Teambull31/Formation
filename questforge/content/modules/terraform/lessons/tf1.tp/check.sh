#!/usr/bin/env bash
set -e

fail() { echo "Erreur: $1" >&2; exit 1; }

[ -f main.tf ] || fail "main.tf introuvable dans l'espace de travail"

grep -Eq '^[[:space:]]*terraform[[:space:]]*\{' main.tf \
  || fail "bloc 'terraform { ... }' manquant"
grep -Eq 'required_version[[:space:]]*=' main.tf \
  || fail "attribut 'required_version' manquant dans le bloc terraform"
grep -Eq 'required_providers[[:space:]]*\{' main.tf \
  || fail "bloc 'required_providers' manquant"
grep -Eq 'source[[:space:]]*=[[:space:]]*"hashicorp/local"' main.tf \
  || fail "provider local non déclaré (source = \"hashicorp/local\")"
grep -Eq 'version[[:space:]]*=[[:space:]]*"' main.tf \
  || fail "contrainte de version du provider manquante"
grep -Eq 'resource[[:space:]]+"local_file"[[:space:]]+"hello"[[:space:]]*\{' main.tf \
  || fail "ressource local_file \"hello\" manquante"
grep -Eq '^[[:space:]]*filename[[:space:]]*=' main.tf \
  || fail "attribut 'filename' manquant dans la ressource"
grep -Eq '^[[:space:]]*content[[:space:]]*=' main.tf \
  || fail "attribut 'content' manquant dans la ressource"

if command -v terraform >/dev/null 2>&1; then
  terraform fmt -check -diff main.tf >/dev/null 2>&1 \
    || fail "format non conforme : lancez 'terraform fmt'"
fi

echo "Vérification réussie : main.tf est une configuration Terraform valide."
exit 0
