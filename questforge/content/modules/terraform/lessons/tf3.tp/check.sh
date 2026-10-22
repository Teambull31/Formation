#!/usr/bin/env bash
set -e

fail() { echo "Erreur: $1" >&2; exit 1; }

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

[ -f secure.tf ] || fail "secure.tf introuvable"
[ -f .gitignore ] || fail ".gitignore introuvable"

pwd_block=$(block_body secure.tf variable db_password)
[ -n "$pwd_block" ] || fail "variable \"db_password\" manquante dans secure.tf"
echo "$pwd_block" | grep -Eq '^[[:space:]]*type[[:space:]]*=[[:space:]]*string' \
  || fail "db_password : 'type = string' manquant"
echo "$pwd_block" | grep -Eq '^[[:space:]]*sensitive[[:space:]]*=[[:space:]]*true' \
  || fail "db_password doit être marquée 'sensitive = true'"
if echo "$pwd_block" | grep -Eq '^[[:space:]]*default[[:space:]]*='; then
  fail "db_password ne doit pas avoir de 'default' : un secret ne se code pas en dur"
fi

grep -Eq 'resource[[:space:]]+"local_sensitive_file"[[:space:]]+"db"[[:space:]]*\{' secure.tf \
  || fail "ressource local_sensitive_file \"db\" manquante"
grep -Eq 'var\.db_password' secure.tf \
  || fail "la ressource doit utiliser var.db_password"

# Aucun secret littéral dans les fichiers .tf
for f in ./*.tf; do
  [ -e "$f" ] || continue
  if grep -Eiq '(password|passwd|secret|token)[[:space:]]*=[[:space:]]*"[^"$]+"' "$f"; then
    fail "secret en dur détecté dans $f : utilisez une variable sensitive"
  fi
done

for pattern in '*.tfstate' '*.tfstate.*' '.terraform/' '*.tfvars'; do
  grep -Fqx -- "$pattern" .gitignore \
    || fail ".gitignore : règle '$pattern' manquante"
done

if command -v terraform >/dev/null 2>&1; then
  terraform fmt -check secure.tf >/dev/null 2>&1 \
    || fail "format non conforme : lancez 'terraform fmt'"
fi

echo "Vérification réussie : secret protégé et state exclu de Git."
exit 0
