# --- GOLD LAYER: Managed PostgreSQL ---
# Dashboard-ready tables. Provenance ledger. VPC for private access.

# --- NETWORK: Private VPC for Postgres ---
resource "google_compute_network" "private_network" {
  name = "medallion-vpc"
}

resource "google_compute_global_address" "private_ip_address" {
  name          = "google-managed-services-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.private_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.private_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# --- Cloud SQL instance ---
resource "google_sql_database_instance" "macrocontext-db-instance" {
  name                = "${var.project_id}-db-instance-${var.env}"
  database_version    = "POSTGRES_15"
  deletion_protection = var.env == "prod" ? false : true
  depends_on          = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier = var.env == "prod" ? "db-custom-2-7680" : "db-f1-micro"
    ip_configuration {
      ipv4_enabled = true
    }
  }
}

resource "google_sql_database" "macrocontext-db" {
  name       = "${var.project_id}-db"
  instance   = google_sql_database_instance.macrocontext-db-instance.name
  depends_on = [google_sql_database_instance.macrocontext-db-instance]
}

resource "google_sql_user" "macrocontext" {
  name     = var.project_id
  instance = google_sql_database_instance.macrocontext-db-instance.name
  password = var.gold_postgres_password
  depends_on = [google_sql_database_instance.macrocontext-db-instance]
}

# --- SQL LEDGER: The Provenance Anchor ---
resource "google_sql_database" "provenance_db" {
  name       = "provenance_ledger"
  instance   = google_sql_database_instance.macrocontext-db-instance.name
  depends_on = [google_sql_database_instance.macrocontext-db-instance]
}

# --- Developer access ---
## Allow Mac to use the High-Speed Read API (BigQuery)
resource "google_project_iam_member" "mac_read_api" {
  project = var.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "user:${var.developer_email}"
}

## Allow Mac to tunnel through Cloud SQL for Postgres access
resource "google_project_iam_member" "mac_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "user:${var.developer_email}"
}
