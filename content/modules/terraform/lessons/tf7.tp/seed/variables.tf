variable "environment" {
  type        = string
  description = "Environnement visé : dev, staging ou prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}

variable "servers" {
  type        = list(string)
  description = "Noms des serveurs web."
}

variable "log_retention_days" {
  type        = number
  description = "Durée de conservation des journaux, en jours."
  default     = 30
}
