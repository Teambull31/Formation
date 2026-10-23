#!/usr/bin/env bash
# Solution de référence, phase 3.
set -euo pipefail
mkdir -p tfboss
cd tfboss
cat > secure.tf <<'EOF'
variable "db_password" {
  type        = string
  description = "Mot de passe de la base, injecté à l'exécution."
  sensitive   = true
}

resource "local_sensitive_file" "db" {
  filename = "${path.module}/db.conf"
  content  = "password=${var.db_password}"
}
EOF
cat > .gitignore <<'EOF'
*.tfstate
*.tfstate.*
.terraform/
*.tfvars
EOF
