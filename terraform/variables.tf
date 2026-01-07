variable "github_owner" {
  description = "GitHub owner (user or organization)"
  type        = string
  default     = "williambrady"
}

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  sensitive   = true
}

variable "config_file" {
  description = "Path to the YAML configuration file"
  type        = string
  default     = "../repositories.yaml"
}

