variable "project_id" { 
  type = string
  default = "macrocontext"
  description = "name of the GCP project"
}

variable "region"     { default = "us-central1" }

variable "env"        { 
  type = string
  description = "gcp cloud environment to deploy to: dev, staging, prod"
  default = "dev"
}

variable "developer_email" {
  type        = string
  description = "email for primary dev account running remotely"
  default     = "joshua@truecodecapital.com"
}

variable "gold_postgres_password" {
  description = "The password for the PostgreSQL user for the gold database"
  type        = string
  sensitive   = true
}
