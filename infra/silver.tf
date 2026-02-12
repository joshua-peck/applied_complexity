# --- SILVER LAYER (GCS + BigLake) ---
# Cleaned, stationarized features and analysis. Domain-shaped, not provider-shaped.

resource "google_storage_bucket" "silver" {
  name                        = "${var.project_id}-silver"
  location                    = "US"
  versioning { enabled = true }
  uniform_bucket_level_access = true
  force_destroy               = var.env == "dev"
}

resource "google_bigquery_dataset" "silver_catalog" {
  dataset_id = "silver_lake"
  project    = var.project_id
  location   = "US"
}

# Expected format:
# gs://{project}-silver/
#   series=us_stocks_sip/
#     frequency=daily/
#       as_of=2026-02-02/
#         stock_features_daily-2026-02-02.parquet
resource "google_bigquery_table" "silver_series_ext" {
  for_each   = var.silver_series
  project    = var.project_id
  dataset_id = google_bigquery_dataset.silver_catalog.dataset_id
  table_id   = "silver_${each.key}_ext"

  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.silver.name}/series=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                     = "AUTO"
      source_uri_prefix         = "gs://${google_storage_bucket.silver.name}/series=${each.key}/"
      require_partition_filter = true
    }
  }
}

# gs://{project}-silver/
#   indicator=gold_to_spx/
#     frequency=daily/
#       as_of=2026-02-02/
#         ...
resource "google_bigquery_table" "silver_indicator_ext" {
  for_each   = var.silver_indicators
  project    = var.project_id
  dataset_id = google_bigquery_dataset.silver_catalog.dataset_id
  table_id   = "silver_${each.key}_ext"

  external_data_configuration {
    source_format = "PARQUET"
    autodetect    = true
    connection_id = google_bigquery_connection.lake_connection.name

    source_uris = [
      "gs://${google_storage_bucket.silver.name}/indicator=${each.key}/*"
    ]

    hive_partitioning_options {
      mode                     = "AUTO"
      source_uri_prefix         = "gs://${google_storage_bucket.silver.name}/indicator=${each.key}/"
      require_partition_filter = true
    }
  }
}

## Grant BigLake permission to read Silver
resource "google_storage_bucket_iam_member" "biglake_read_silver" {
  bucket = google_storage_bucket.silver.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.lake_connection.cloud_resource[0].service_account_id}"
}
