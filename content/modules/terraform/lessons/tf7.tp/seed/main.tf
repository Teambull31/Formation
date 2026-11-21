terraform {
  required_version = ">= 1.6"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 9.0"
    }
  }
}

locals {
  out_dir = "${path.module}/out"
}

# Renommée hier de « logs » en « journaux » pour suivre la convention de l'équipe.
resource "local_file" "journaux" {
  filename = "${local.out_dir}/logs.conf"
  content  = "retention=${var.log_retention_days}\n"
}

resource "local_file" "server" {
  count    = length(var.servers)
  filename = "${local.out_dir}/${var.servers[count.index]}.conf"
  content  = "env=${var.environment}\n"
}

resource "local_file" "config" {
  filename = "${local.out_dir}/app.conf"
  content  = "env=${var.environment}\nreplicas=2\n"
}
