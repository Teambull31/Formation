variable "app_name" {
  type        = string
  description = "Nom de l'application."
}

variable "environment" {
  type        = string
  description = "Environnement visé."
}

variable "port" {
  type        = number
  description = "Port d'écoute."
  default     = 8080
}
