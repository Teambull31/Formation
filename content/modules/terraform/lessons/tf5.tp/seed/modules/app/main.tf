resource "local_file" "config" {
  filename = "${path.module}/out/${var.app_name}-${var.environment}.conf"
  content  = "app=${var.app_name}\nenv=${var.environment}\nport=${var.port}\n"
}
