#!/usr/bin/env bash
# Solution de référence, phase 1.
set -euo pipefail
mkdir -p tfboss
cd tfboss
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

resource "local_file" "hello" {
  filename = "${path.module}/hello.txt"
  content  = "Bonjour IaC"
}
EOF
