 terraform {
  backend "gcs" {
    bucket = "appliedcomplexity-tfstate"
    prefix = "terraform/state"
  }
}
