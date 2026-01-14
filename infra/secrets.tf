resource "google_secret_manager_secret" "fred_api_key" {
  secret_id = "FRED_API_KEY"
  replication {
    user_managed {
      replicas {
        location = "us-central1"
      }
    }
  }
}

# Grant the Cloud Run Service Account permission to read it
resource "google_secret_manager_secret_iam_member" "accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.fred_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "user:${var.developer_email}"
}