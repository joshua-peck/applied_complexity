# --- PROCESSORS ---
# Cloud Run Job for stock_features_daily, triggered daily by Cloud Scheduler.

resource "google_cloud_run_v2_job" "stock_features_daily" {
  name     = "processor-stock-features-daily"
  location = var.region
  deletion_protection  = var.env == "prod"
  template {
    task_count = 1
    template {
      containers {
        name  = "stock-features"
        image = "${local.pipeline_image_base}/processors:${var.pipeline_image_tag}"
        command = ["python", "mc.py"]
        args    = ["processors", "stock_features_daily"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "SILVER_BUCKET"
          value = google_storage_bucket.silver.name
        }
        env {
          name  = "BRONZE_DATA_LAKE"
          value = google_bigquery_dataset.bronze_catalog.dataset_id
        }
        env {
          name  = "BRONZE_BQ_TABLE"
          value = "bronze_massive_ext"
        }
        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }
      }
      timeout      = "1200s"
      max_retries  = 2
      service_account = google_service_account.pipeline.email
    }
  }
}

resource "google_cloud_scheduler_job" "stock_features_daily" {
  name             = "processor-stock-features-daily"
  region           = var.region
  schedule         = "0 16 * * *"  # 4 PM UTC daily (11 AM ET), after ingestors
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.stock_features_daily.name}:run"
    oidc_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.cloud_scheduler]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_stock_features" {
  location = google_cloud_run_v2_job.stock_features_daily.location
  name     = google_cloud_run_v2_job.stock_features_daily.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}
