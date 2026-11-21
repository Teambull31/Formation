#!/usr/bin/env bash
# Solution de référence du TP tf4.
set -euo pipefail
cat > main.tf <<'EOF'
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

locals {
  out_dir = "${path.module}/out"
}

resource "local_file" "config" {
  for_each = var.environments
  filename = "${local.out_dir}/${each.key}.conf"
  content  = "app=${var.app_name}\nreplicas=${each.value.replicas}\ndebug=${each.value.debug}\n"
}
EOF
cat > variables.tf <<'EOF'
variable "app_name" {
  type        = string
  description = "Nom de l'application."
  default     = "shop"
}

variable "environments" {
  type = map(object({
    replicas = number
    debug    = bool
  }))
  description = "Paramètres par environnement."
}
EOF
cat > outputs.tf <<'EOF'
output "config_files" {
  description = "Fichier de configuration de chaque environnement."
  value       = { for env, f in local_file.config : env => f.filename }
}
EOF
