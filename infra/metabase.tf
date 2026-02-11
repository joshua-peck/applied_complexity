variable "metabase_image" {
  type    = string
  default = "metabase/metabase:latest"
}

variable "metabase_db_password" {
  description = "The password for the Metabase database user"
  type        = string
  sensitive   = true
}

resource "google_sql_database" "metabase_app_db" {
  name     = "metabase_app"
  instance = google_sql_database_instance.macrocontext-db-instance.name
}

resource "google_sql_user" "metabase_user" {
  name     = "metabase"
  instance = google_sql_database_instance.macrocontext-db-instance.name
  password = var.metabase_db_password
}

resource "google_secret_manager_secret" "metabase_db_password" {
  secret_id = "METABASE_DB_PASSWORD"
  replication {
    user_managed {
      replicas {
        location = "us-central1"
      }
    }
  }
}

resource "google_secret_manager_secret_version" "metabase_db_password_v1" {
  secret      = google_secret_manager_secret.metabase_db_password.id
  secret_data = var.metabase_db_password
}

resource "google_service_account" "metabase_sa" {
  account_id   = "metabase-sa"
  display_name = "Metabase Cloud Run SA"
}

# Allow SA to connect to Cloud SQL
resource "google_project_iam_member" "metabase_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.metabase_sa.email}"
}

# Allow SA to read the DB password secret
resource "google_secret_manager_secret_iam_member" "metabase_secret_access" {
  secret_id = google_secret_manager_secret.metabase_db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.metabase_sa.email}"
}

resource "google_cloud_run_v2_service" "metabase" {
  name     = "metabase"
  location = var.region

  template {
    service_account = google_service_account.metabase_sa.email

    scaling {
      min_instance_count = 1
      max_instance_count = 3
    }

    # --- Metabase container ---
    containers {
      name  = "metabase"
      image = var.metabase_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      # Metabase listens on Cloud Run's port (8080)
      env {
        name  = "MB_JETTY_PORT"
        value = "8080"
      }

      # Metabase app DB settings (connect to proxy on localhost)
      env {
        name  = "MB_DB_TYPE"
        value = "postgres"
      }

      env {
        name  = "MB_DB_DBNAME"
        value = google_sql_database.metabase_app_db.name
      }

      env {
        name  = "MB_DB_USER"
        value = google_sql_user.metabase_user.name
      }

      env {
        name  = "MB_DB_HOST"
        value = "127.0.0.1"
      }

      env {
        name  = "MB_DB_PORT"
        value = "5432"
      }

      env {
        name = "MB_DB_PASS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.metabase_db_password.secret_id
            version = "latest"
          }
        }
      }
    }

    # --- Cloud SQL Auth Proxy sidecar ---
    containers {
      name  = "cloud-sql-proxy"
      image = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.11.4"

      # No need to expose ports; it listens on localhost inside the service
      args = [
        "--address=127.0.0.1",
        "--port=5432",
        google_sql_database_instance.macrocontext-db-instance.connection_name
      ]

      resources {
        limits = {
          cpu    = "0.25"
          memory = "256Mi"
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [
    google_project_iam_member.metabase_cloudsql_client,
    google_secret_manager_secret_iam_member.metabase_secret_access,
    google_secret_manager_secret_version.metabase_db_password_v1,
    google_sql_database.metabase_app_db,
    google_sql_user.metabase_user,
  ]
}

# # Optional: make Metabase public
resource "google_cloud_run_v2_service_iam_member" "metabase_public" {
  location = google_cloud_run_v2_service.metabase.location
  name     = google_cloud_run_v2_service.metabase.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# resource "google_cloud_run_v2_service_iam_member" "metabase_me_invoker" {
#   location = google_cloud_run_v2_service.metabase.location
#   name     = google_cloud_run_v2_service.metabase.name
#   role     = "roles/run.invoker"
#   member   = "user:joshua@truecodecapital.com"
# }

output "metabase_url" {
  value = google_cloud_run_v2_service.metabase.uri
}

# resource "google_cloud_run_v2_service_iam_member" "metabase_domain_invoker" {
#   location = google_cloud_run_v2_service.metabase.location
#   name     = google_cloud_run_v2_service.metabase.name
#   role     = "roles/run.invoker"
#   member   = "domain:truecodecapital.com"
# }

# resource "google_cloud_run_service" "metabase" {
#   name     = "metabase"
#   location = var.region
#   depends_on = [google_secret_manager_secret.metabase_db_password]

#   template {
#     spec {
#       service_account_name = google_service_account.metabase_sa.email

#       containers {
#         image = var.metabase_image

#         ports {
#           container_port = 3000
#         }

#         resources {
#           limits = {
#             memory = "1Gi"
#           }
#         }

#         env { 
#           name = "MB_DB_TYPE"   
#           value = "postgres"
#         }
#         env { 
#           name = "MB_DB_DBNAME" 
#           value = "metabase_app" 
#         }
#         env { 
#           name = "MB_DB_USER"   
#           value = google_sql_user.metabase_user.name 
#         }
#         env { 
#           name = "MB_DB_PORT"   
#           value = "5432" 
#         }

#         # Cloud SQL unix socket path
#         env {
#           name  = "MB_DB_HOST"
#           # value = "/cloudsql/${google_sql_database_instance.macrocontext-db-instance.connection_name}"
#           value = "localhost"
#         }

#         # Password from Secret Manager
#         env {
#           name = "MB_DB_PASS"
#           value_from {
#             secret_key_ref {
#               name = google_secret_manager_secret.metabase_db_password.secret_id
#               key  = "latest"
#             }
#           }
#         }
#       }
#     }

#     metadata {
#       annotations = {
#         # Attach Cloud SQL instance to Cloud Run
#         "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.macrocontext-db-instance.connection_name
#       }
#     }
#   }

#   traffic {
#     percent         = 100
#     latest_revision = true
#   }

#   autogenerate_revision_name = true
# }

