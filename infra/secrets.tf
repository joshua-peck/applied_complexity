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

resource "google_secret_manager_secret" "gold_postgres_password" {
  secret_id = "GOLD_POSTGRES_PASSWORD"
  replication {
    user_managed {
      replicas {
        location = "us-central1"
      }
    }
  }
}

resource "google_secret_manager_secret_version" "gold_postgres_password_val" {
  secret      = google_secret_manager_secret.gold_postgres_password.id
  secret_data = var.gold_postgres_password
}

# Grant the Cloud Run Service Account permission to read it
resource "google_secret_manager_secret_iam_member" "accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.fred_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "user:${var.developer_email}"
}