# Fourni : la ressource que le module expose. Ne la modifiez pas.
resource "local_file" "config" {
  filename = "${path.module}/${var.app_name}-${var.environment}.conf"
  content  = "app=${var.app_name}\nenv=${var.environment}\n"
}
