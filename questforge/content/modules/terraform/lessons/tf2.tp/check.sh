#!/usr/bin/env bash
set -e

fail() { echo "Erreur: $1" >&2; exit 1; }

# Extrait le corps d'un bloc HCL de premier niveau : block_body <fichier> <type> <nom>
block_body() {
  awk -v t="$2" -v n="$3" '
    $0 ~ "^[[:space:]]*" t "[[:space:]]+\"" n "\"[[:space:]]*\\{" { inblk = 1; depth = 0 }
    inblk {
      print
      depth += gsub(/\{/, "{") - gsub(/\}/, "}")
      if (depth <= 0) exit
    }
  ' "$1"
}

[ -f variables.tf ] || fail "variables.tf introuvable"
[ -f outputs.tf ] || fail "outputs.tf introuvable"

app=$(block_body variables.tf variable app_name)
[ -n "$app" ] || fail "variable \"app_name\" manquante dans variables.tf"
echo "$app" | grep -Eq '^[[:space:]]*type[[:space:]]*=[[:space:]]*string' \
  || fail "app_name : 'type = string' manquant"
echo "$app" | grep -Eq '^[[:space:]]*description[[:space:]]*=[[:space:]]*"[^"]+"' \
  || fail "app_name : 'description' absente ou vide"
echo "$app" | grep -Eq '^[[:space:]]*default[[:space:]]*=' \
  || fail "app_name : 'default' manquant"

env=$(block_body variables.tf variable environment)
[ -n "$env" ] || fail "variable \"environment\" manquante dans variables.tf"
echo "$env" | grep -Eq '^[[:space:]]*type[[:space:]]*=[[:space:]]*string' \
  || fail "environment : 'type = string' manquant"
echo "$env" | grep -Eq '^[[:space:]]*description[[:space:]]*=[[:space:]]*"[^"]+"' \
  || fail "environment : 'description' absente ou vide"
if echo "$env" | grep -Eq '^[[:space:]]*default[[:space:]]*='; then
  fail "environment doit être obligatoire : retirez son 'default'"
fi

out=$(block_body outputs.tf output config_path)
[ -n "$out" ] || fail "output \"config_path\" manquant dans outputs.tf"
echo "$out" | grep -Eq '^[[:space:]]*description[[:space:]]*=[[:space:]]*"[^"]+"' \
  || fail "config_path : 'description' absente ou vide"
echo "$out" | grep -Eq '^[[:space:]]*value[[:space:]]*=[[:space:]]*[^[:space:]]+' \
  || fail "config_path : 'value' manquant"

if command -v terraform >/dev/null 2>&1; then
  terraform fmt -check variables.tf outputs.tf >/dev/null 2>&1 \
    || fail "format non conforme : lancez 'terraform fmt'"
fi

echo "Vérification réussie : le contrat du module est correctement défini."
exit 0
