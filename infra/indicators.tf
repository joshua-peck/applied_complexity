# --- INDICATORS ---
# Cloud Run Job for spx_gold_daily, triggered daily by Cloud Scheduler.

resource "google_cloud_run_v2_job" "spx_gold_daily" {
  name     = "indicator-spx-gold-daily"
  location = var.region
  deletion_protection  = var.env == "prod"
  template {
    task_count = 1
    template {
      containers {
        name  = "spx-gold"
        image = "${local.pipeline_image_base}/indicators:${var.pipeline_image_tag}"
        command = ["python", "mc.py"]
        args    = ["indicators", "spx_gold_daily"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "SILVER_BUCKET"
          value = google_storage_bucket.silver.name
        }
        env {
          name  = "SILVER_DATA_LAKE"
          value = google_bigquery_dataset.silver_catalog.dataset_id
        }
        env {
          name  = "SILVER_BQ_TABLE"
          value = "silver_us_stocks_sip_ext"
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
      timeout      = "600s"
      max_retries  = 2
      service_account = google_service_account.pipeline.email
    }
  }
}

resource "google_cloud_scheduler_job" "spx_gold_daily" {
  name             = "indicator-spx-gold-daily"
  region           = var.region
  schedule         = "0 17 * * *"  # 5 PM UTC daily (12 PM ET), after processors
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.spx_gold_daily.name}:run"
    oidc_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.cloud_scheduler]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_spx_gold" {
  location = google_cloud_run_v2_job.spx_gold_daily.location
  name     = google_cloud_run_v2_job.spx_gold_daily.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}
