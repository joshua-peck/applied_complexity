variable "project_id" { type = string }
variable "region"     { default = "us-central1" }
variable "env"        { type = string } # dev, staging, or prod
variable "developer_email" {
  type        = string
  description = "email for primary dev account running remotely"
  default     = "joshua@truecodecapital.com"
}