# --- INGESTORS ---
# Cloud Run Jobs for fred + massive, triggered daily by Cloud Scheduler.

resource "google_cloud_run_v2_job" "fred" {
  name     = "ingestor-fred"
  location = var.region
  deletion_protection = var.env == "prod"
  template {
    task_count = 1
    template {
      containers {
        name  = "fred"
        image = "${local.pipeline_image_base}/ingestors:${var.pipeline_image_tag}"
        command = ["python", "mc.py"]
        args    = ["ingestors", "fred"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "LANDING_ZONE_BUCKET"
          value = google_storage_bucket.landing_zone.name
        }
        env {
          name  = "BRONZE_BUCKET"
          value = google_storage_bucket.bronze.name
        }
        env {
          name = "FRED_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.fred_api_key.secret_id
              version = "latest"
            }
          }
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
      timeout         = "600s"
      max_retries     = 2
      service_account = google_service_account.pipeline.email
    }
  }
  depends_on = [
    google_secret_manager_secret_iam_member.pipeline_fred,
  ]
}

resource "google_cloud_run_v2_job" "massive" {
  name     = "ingestor-massive"
  location = var.region
  deletion_protection = var.env == "prod"
  template {
    task_count = 1
    template {
      containers {
        name  = "massive"
        image = "${local.pipeline_image_base}/ingestors:${var.pipeline_image_tag}"
        command = ["python", "mc.py"]
        args    = ["ingestors", "massive"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "LANDING_ZONE_BUCKET"
          value = google_storage_bucket.landing_zone.name
        }
        env {
          name  = "BRONZE_BUCKET"
          value = google_storage_bucket.bronze.name
        }
        env {
          name = "MASSIVE_ACCESS_KEY_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.massive_access_key.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "MASSIVE_SECRET_ACCESS_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.massive_secret_key.secret_id
              version = "latest"
            }
          }
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
      timeout         = "900s"
      max_retries     = 2
      service_account = google_service_account.pipeline.email
    }
  }
  depends_on = [
    google_secret_manager_secret_iam_member.pipeline_massive_access,
    google_secret_manager_secret_iam_member.pipeline_massive_secret,
  ]
}

resource "google_cloud_scheduler_job" "fred_daily" {
  name             = "ingestor-fred-daily"
  region           = var.region
  schedule         = "0 14 * * *"  # 2 PM UTC daily (9 AM ET)
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.fred.name}:run"
    oidc_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.cloud_scheduler]
}

resource "google_cloud_scheduler_job" "massive_daily" {
  name             = "ingestor-massive-daily"
  region           = var.region
  schedule         = "0 15 * * *"  # 3 PM UTC daily (10 AM ET), after fred
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.massive.name}:run"
    oidc_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.cloud_scheduler]
}

# Cloud Scheduler needs run.invoker to trigger jobs
resource "google_cloud_run_v2_job_iam_member" "scheduler_fred" {
  location = google_cloud_run_v2_job.fred.location
  name     = google_cloud_run_v2_job.fred.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_massive" {
  location = google_cloud_run_v2_job.massive.location
  name     = google_cloud_run_v2_job.massive.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}
