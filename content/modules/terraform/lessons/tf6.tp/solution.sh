#!/usr/bin/env bash
# Solution de référence du TP tf6.
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

moved {
  from = local_file.hello
  to   = local_file.greeting
}

resource "local_file" "greeting" {
  filename = "${path.module}/out/hello-${var.environment}.txt"
  content  = "Bonjour ${var.environment}"
}

resource "local_file" "db_config" {
  filename = "${path.module}/out/db-${var.environment}.conf"
  content  = "port=5432\n"
  lifecycle {
    prevent_destroy = true
  }
}
EOF
cat > variables.tf <<'EOF'
variable "environment" {
  type        = string
  description = "Environnement visé : dev, staging ou prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}
EOF
mkdir -p .github/workflows
cat > .github/workflows/terraform.yml <<'EOF'
name: Terraform
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd
      - run: terraform fmt -check -recursive
      - run: terraform init -input=false
      - run: terraform validate
      - run: terraform plan -input=false -out=tfplan
  apply:
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: production
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd
      - run: terraform init -input=false
      - run: terraform apply -input=false -auto-approve
EOF
