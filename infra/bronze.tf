# --- BRONZE LAYER (GCS + BigLake) ---
# Canonical, queryable snapshots by provider. Source of truth for replay.

resource "google_storage_bucket" "bronze" {
  name                        = "${var.project_id}-bronze"
  location                    = "US"
  versioning { enabled = true }
  uniform_bucket_level_access = true
  force_destroy               = var.env == "dev"
}

# BigLake connection for GCS → BigQuery (shared by bronze and silver)
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
  for_each   = var.data_providers
  project    = var.project_id
  dataset_id = google_bigquery_dataset.bronze_catalog.dataset_id
  table_id   = "bronze_${each.key}_ext"

  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.bronze.name}/provider=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                     = "AUTO"
      source_uri_prefix         = "gs://${google_storage_bucket.bronze.name}/provider=${each.key}/"
      require_partition_filter = true
    }
  }
}

## Grant BigLake permission to read Bronze
resource "google_storage_bucket_iam_member" "biglake_read" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
}

## BigQuery Metadata access for schema evolution
resource "google_project_iam_member" "biglake_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
}
