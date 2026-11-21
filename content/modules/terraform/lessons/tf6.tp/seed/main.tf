terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# Cette ressource s'appelait local_file.hello : le state la connaît encore sous ce nom.
resource "local_file" "greeting" {
  filename = "${path.module}/out/hello-${var.environment}.txt"
  content  = "Bonjour ${var.environment}"
}

# Contient la configuration de la base : ne doit jamais être détruite par erreur.
resource "local_file" "db_config" {
  filename = "${path.module}/out/db-${var.environment}.conf"
  content  = "port=5432\n"
}
