# --- PUBLISHERS ---
# Cloud Run Job for spx_gold_trend, triggered daily by Cloud Scheduler.
# Uses Cloud SQL volume for Postgres connection.

resource "google_cloud_run_v2_job" "spx_gold_trend" {
  name     = "publisher-spx-gold-trend"
  location = var.region
  deletion_protection  = var.env == "prod"
  template {
    task_count = 1
    template {
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.macrocontext-db-instance.connection_name]
        }
      }
      containers {
        name  = "spx-gold-trend"
        image = "${local.pipeline_image_base}/publishers:${var.pipeline_image_tag}"
        command = ["python", "mc.py"]
        args    = ["publishers", "spx_gold_trend"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "REGION"
          value = var.region
        }
        env {
          name  = "SILVER_DATA_LAKE"
          value = google_bigquery_dataset.silver_catalog.dataset_id
        }
        env {
          name  = "SILVER_BQ_INDICATOR_TABLE"
          value = "silver_gold_to_spx_ext"
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.macrocontext-db-instance.connection_name
        }
        env {
          name  = "GOLD_POSTGRES_USER"
          value = google_sql_user.macrocontext.name
        }
        env {
          name  = "GOLD_POSTGRES_DB"
          value = google_sql_database.macrocontext-db.name
        }
        env {
          name = "GOLD_POSTGRES_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gold_postgres_password.secret_id
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
      timeout      = "300s"
      max_retries  = 2
      service_account = google_service_account.pipeline.email
    }
  }
  depends_on = [
    google_secret_manager_secret_iam_member.pipeline_gold_postgres,
  ]
}

resource "google_cloud_scheduler_job" "spx_gold_trend_daily" {
  name             = "publisher-spx-gold-trend-daily"
  region           = var.region
  schedule         = "0 18 * * *"  # 6 PM UTC daily (1 PM ET), after indicators
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.spx_gold_trend.name}:run"
    oidc_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.cloud_scheduler]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_spx_gold_trend" {
  location = google_cloud_run_v2_job.spx_gold_trend.location
  name     = google_cloud_run_v2_job.spx_gold_trend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline.email}"
}
