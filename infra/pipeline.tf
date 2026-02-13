# --- PIPELINE: Shared infra for daily jobs ---
# Artifact Registry, service account, APIs. Jobs are defined in ingestors/processors/indicators/publishers.

locals {
  pipeline_image_base = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.pipeline.repository_id}"
}

resource "google_project_service" "artifact_registry" {
  project = var.project_id
  service = "artifactregistry.googleapis.com"
}

resource "google_project_service" "cloud_scheduler" {
  project = var.project_id
  service = "cloudscheduler.googleapis.com"
}

resource "google_artifact_registry_repository" "pipeline" {
  project       = var.project_id
  location      = var.region
  repository_id = "pipeline"
  description   = "Pipeline images: ingestors, processors, indicators, publishers"
  format        = "DOCKER"

  depends_on = [google_project_service.artifact_registry]
}

resource "google_service_account" "pipeline" {
  account_id   = "pipeline-sa"
  display_name = "Pipeline Cloud Run Jobs SA"
}

# Storage: landing zone, bronze, silver
resource "google_storage_bucket_iam_member" "pipeline_landing" {
  bucket = google_storage_bucket.landing_zone.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_bronze" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_silver" {
  bucket = google_storage_bucket.silver.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

# BigQuery
resource "google_project_iam_member" "pipeline_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# Cloud SQL (for publishers)
resource "google_project_iam_member" "pipeline_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# Secrets (FRED, Massive, Gold Postgres)
resource "google_secret_manager_secret_iam_member" "pipeline_fred" {
  secret_id = google_secret_manager_secret.fred_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_secret_manager_secret_iam_member" "pipeline_gold_postgres" {
  secret_id = google_secret_manager_secret.gold_postgres_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_secret_manager_secret_iam_member" "pipeline_massive_access" {
  secret_id = google_secret_manager_secret.massive_access_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_secret_manager_secret_iam_member" "pipeline_massive_secret" {
  secret_id = google_secret_manager_secret.massive_secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}
