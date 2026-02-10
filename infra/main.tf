provider "google" {
  project = var.project_id
  region  = var.region
}

# --- 0. LANDING BUCKET: Pristine Archive
resource "google_storage_bucket" "landing_zone" {
  name                        = "${var.project_id}-landing-zone"
  location                    = "US"
  storage_class               = "STANDARD" # Start standard, move to archive via lifecycle
  uniform_bucket_level_access = true

  # IMMUTABILITY: Prevent deletion/overwrites for 5 years in prod only
  dynamic "retention_policy" {
    # If prod, create a list with 1 element; if not, create an empty list []
    for_each = var.env == "prod" ? [1] : []
    content {
      is_locked        = false # Caution: setting to true makes removal irreversible
      retention_period = 157680000 # 5 years in seconds in prod
    }
  }

  # ARCHIVAL: Move to Archive class after 30 days to save costs
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }
}

# --- 1. BRONZE/SILVER LAYER (GCS) ---
resource "google_storage_bucket" "bronze" {
  name     = "${var.project_id}-bronze"
  location = "US"
  versioning { enabled = true }
  uniform_bucket_level_access = true
  force_destroy = var.env == "dev"
}

resource "google_storage_bucket" "silver" {
  name     = "${var.project_id}-silver"
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

resource "google_bigquery_dataset" "bronze_catalog" {
  dataset_id = "bronze_lake"
  project    = var.project_id
  location   = "US"
}

resource "google_bigquery_dataset" "silver_catalog" {
  dataset_id = "silver_lake"
  project    = var.project_id
  location   = "US"
}

# Create local vars to query providers interchangeably
variable "data_providers" {
  type    = set(string)
  default = ["fred", "massive"]
}

# Expected format:
# gs://<project>-bronze/
#   provider=massive/
#     series=TSLA/
#       frequency=Daily/
#         issued_date=2026-01-09/
#           ingest_date=2026-01-22/
#             2026-01-09.parquet
# TODO: Standardize frequency strings between providers
resource "google_bigquery_table" "bronze_provider_ext" {
  for_each  = var.data_providers
  project   = var.project_id
  dataset_id = google_bigquery_dataset.bronze_catalog.dataset_id
  table_id  = "bronze_${each.key}_ext"

  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.bronze.name}/provider=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                    = "AUTO"
      source_uri_prefix        = "gs://${google_storage_bucket.bronze.name}/provider=${each.key}/"
      require_partition_filter = true
    }
  }
}

# Expected format:
# gs://{project}-silver/
#   series=us_stocks_sip/
#     frequency=daily/
#       as_of=2026-02-02/
#         stock_features_daily-2026-02-02.parquet
variable "silver_series" {
  type    = set(string)
  default = ["us_stocks_sip"]
}

resource "google_bigquery_table" "silver_series_ext" {
  for_each  = var.silver_series
  project   = var.project_id
  dataset_id = google_bigquery_dataset.silver_catalog.dataset_id
  table_id  = "silver_${each.key}_ext"
  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.silver.name}/series=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                    = "AUTO"
      source_uri_prefix        = "gs://${google_storage_bucket.silver.name}/series=${each.key}/"
      require_partition_filter = true
    }
  }
}

# gs://{project}-silver/
#   indicator=spx_gold_pair/
#     frequency=daily/
#       as_of=2026-02-02/
#         stock_features_daily-2026-02-02.parquet
variable "silver_indicators" {
  type    = set(string)
  default = ["gold_to_spx"]
}

resource "google_bigquery_table" "silver_indicator_ext" {
  for_each  = var.silver_indicators
  project   = var.project_id
  dataset_id = google_bigquery_dataset.silver_catalog.dataset_id
  table_id  = "silver_${each.key}_ext"
  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.silver.name}/indicator=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                    = "AUTO"
      source_uri_prefix        = "gs://${google_storage_bucket.silver.name}/indicator=${each.key}/"
      require_partition_filter = true
    }
  }
}

# --- 3. NETWORK: Private VPC for Postgres
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

# --- 4. GOLD LAYER: Managed PostgreSQL
resource "google_sql_database_instance" "macrocontext-db" {
  name             = "macrocontext-${var.env}"
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

# --- 5. SQL LEDGER: The Provenance Anchor
resource "google_sql_database" "provenance_db" {
  name     = "provenance_ledger"
  instance = google_sql_database_instance.macrocontext-db.name
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

## Grant BigLake permission to read Silver
resource "google_storage_bucket_iam_member" "biglake_read_silver" {
  bucket = google_storage_bucket.silver.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
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
  member  = "user:${var.developer_email}"
}