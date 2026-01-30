 terraform {
  backend "gcs" {
    bucket = "macrocontext-tfstate"
    prefix = "terraform/state"
  }
}
