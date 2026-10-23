#!/usr/bin/env bash
# Solution de référence, phase 2.
set -euo pipefail
mkdir -p tfboss
cd tfboss
cat > variables.tf <<'EOF'
variable "app_name" {
  type        = string
  description = "Nom de l'application, préfixe des fichiers générés."
  default     = "demo"
}

variable "environment" {
  type        = string
  description = "Environnement visé : dev, test ou prod."
}
EOF
cat > outputs.tf <<'EOF'
output "config_path" {
  description = "Chemin du fichier de configuration généré."
  value       = local_file.hello.filename
}
EOF
