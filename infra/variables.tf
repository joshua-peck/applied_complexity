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

variable "pipeline_image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for pipeline images (ingestors, processors, indicators, publishers)"
}

# --- Medallion / data layer ---
variable "data_providers" {
  type        = set(string)
  default     = ["fred", "massive"]
  description = "Data providers with bronze external tables"
}

variable "silver_series" {
  type        = set(string)
  default     = ["us_stocks_sip"]
  description = "Silver series (e.g. from feature processors)"
}

variable "silver_indicators" {
  type        = set(string)
  default     = ["gold_to_spx"]
  description = "Silver indicator names (e.g. from indicator jobs)"
}
