locals {
  developer_email = "joshua@truecodecapital.com"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- 1. BRONZE LAYER (GCS) ---
resource "google_storage_bucket" "bronze" {
  name     = "${var.project_id}-bronze"
  location = "US"
  versioning { enabled = true }
  uniform_bucket_level_access = true
  force_destroy = var.env == "dev"
}

# --- 2. BIGLAKE CONNECTION ---
resource "google_bigquery_connection" "lake_connection" {
  connection_id = "medallion-bridge"
  location      = "US"
  cloud_resource {}
}

# 3. NETWORK: Private VPC for Postgres
resource "google_compute_network" "private_network" {
  name = "medallion-vpc"
}

resource "google_compute_global_address" "private_ip_address" {
  name          = "google-managed-services-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.private_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.private_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# 4. SILVER/GOLD LAYER: Managed PostgreSQL
resource "google_sql_database_instance" "appliedcomplexity-db" {
  name             = "appliedcomplexity-${var.env}"
  database_version = "POSTGRES_15"
  depends_on       = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier = var.env == "prod" ? "db-custom-2-7680" : "db-f1-micro"
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.private_network.id
    }
  }
}

## Grant BigLake permission to read Bronze
resource "google_storage_bucket_iam_member" "biglake_read" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
}

## (Optional) Grant BigQuery Metadata access - useful for schema evolution
resource "google_project_iam_member" "biglake_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
}

## Allow your Mac to use the High-Speed Read API (Free Tier)
resource "google_project_iam_member" "mac_read_api" {
  project = var.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "user:${var.developer_email}"
}

## Allow Mac to tunnel through Private VPC for Postgres access
resource "google_project_iam_member" "mac_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "user:${local.developer_email}"
}

