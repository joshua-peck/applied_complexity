# --- LANDING ZONE: Pristine Archive ---
# Original, bit-for-bit API payloads. Immutable evidence locker.

resource "google_storage_bucket" "landing_zone" {
  name                        = "${var.project_id}-landing-zone"
  location                    = "US"
  storage_class               = "STANDARD" # Start standard, move to archive via lifecycle
  uniform_bucket_level_access = true

  # IMMUTABILITY: Prevent deletion/overwrites for 5 years in prod only
  dynamic "retention_policy" {
    for_each = var.env == "prod" ? [1] : []
    content {
      is_locked        = false # Caution: setting to true makes removal irreversible
      retention_period = 157680000 # 5 years in seconds in prod
    }
  }

  # ARCHIVAL: Move to Archive class after 30 days to save costs
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }
}
