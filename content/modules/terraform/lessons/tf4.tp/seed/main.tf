terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

resource "local_file" "dev" {
  filename = "${path.module}/out/dev.conf"
  content  = "app=shop\nreplicas=1\ndebug=true\n"
}

resource "local_file" "staging" {
  filename = "${path.module}/out/staging.conf"
  content  = "app=shop\nreplicas=2\ndebug=true\n"
}

resource "local_file" "prod" {
  filename = "${path.module}/out/prod.conf"
  content  = "app=shop\nreplicas=3\ndebug=false\n"
}
