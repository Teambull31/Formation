#!/usr/bin/env bash
# Solution de référence, étape 4 du projet : l'infrastructure en Terraform.
set -euo pipefail
LESSON_DIR="$LESSON_DIR/../pr3.tp" bash "$LESSON_DIR/../pr3.tp/solution.sh"
mkdir -p infra
cat > infra/main.tf <<'TF'
terraform {
  required_version = ">= 1.6"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
  backend "s3" {
    bucket       = "moncompte-tfstate"
    key          = "commandes/prod.tfstate"
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
  }
}

locals {
  servers = toset(["web-1", "web-2"])
}

resource "local_file" "server" {
  for_each = local.servers
  filename = "${path.module}/out/${each.key}.ini"
  content  = "env=${var.environment}\n"
}
TF
cat > infra/variables.tf <<'TF'
variable "environment" {
  type        = string
  description = "Environnement visé : dev, staging ou prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}
TF
cat > infra/outputs.tf <<'TF'
output "web_servers" {
  description = "Noms des serveurs web, lus pour générer l'inventaire Ansible."
  value       = sort(keys(local_file.server))
}
TF
printf '.terraform/\n*.tfstate\n*.tfstate.*\n*.tfvars\n.env\n' > .gitignore
