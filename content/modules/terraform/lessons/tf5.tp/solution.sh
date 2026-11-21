#!/usr/bin/env bash
# Solution de référence du TP tf5.
set -euo pipefail
cat > modules/app/outputs.tf <<'EOF'
output "config_path" {
  description = "Chemin du fichier de configuration généré."
  value       = local_file.config.filename
}
EOF
cat > main.tf <<'EOF'
terraform {
  required_version = ">= 1.10.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
  backend "s3" {
    bucket       = "acme-tfstate"
    key          = "web/prod.tfstate"
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
  }
}

module "web" {
  source      = "./modules/app"
  app_name    = "web"
  environment = var.environment
}

module "naming" {
  source = "git::https://git.example.test/infra/modules.git//naming?ref=v1.2.0"
  prefix = "acme"
}
EOF
cat > outputs.tf <<'EOF'
output "web_config" {
  description = "Chemin du fichier de configuration de web."
  value       = module.web.config_path
}
EOF
