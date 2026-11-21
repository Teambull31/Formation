terraform {
  required_version = ">= 1.10.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
  backend "s3" {
    bucket     = "acme-tfstate"
    key        = "terraform.tfstate"
    region     = "eu-west-3"
    access_key = "CLE-A-RETIRER"
    secret_key = "SECRET-A-RETIRER"
  }
}

module "web" {
  source   = "./modules/app"
  app_name = "web"
  replicas = 3
}

module "naming" {
  source = "git::https://git.example.test/infra/modules.git//naming"
  prefix = "acme"
}
