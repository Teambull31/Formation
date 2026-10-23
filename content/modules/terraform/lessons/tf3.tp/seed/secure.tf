# Dépôt hérité : ce fichier fuit un secret. Corrigez-le.
variable "db_password" {
  type    = string
  default = "changeme123"
}

resource "local_sensitive_file" "db" {
  filename = "${path.module}/db.conf"
  content  = "password=changeme123"
}
