# INFRA LAYOUT (TERRAFORM)

| File | Purpose |
|------|--------|
| `main.tf` | Provider config only |
| `landing_zone.tf` | Landing bucket (immutable archive) |
| `bronze.tf` | Bronze GCS bucket, BigLake connection, bronze catalog + external tables, IAM |
| `silver.tf` | Silver GCS bucket, silver catalog + series/indicator external tables, IAM |
| `gold.tf` | VPC, Cloud SQL, gold + provenance DBs, dev IAM |
| `metabase.tf` | Metabase app DB, SA, Cloud Run, secrets |
| `ingestors.tf` | Placeholder for ingest job infra (Cloud Run, Scheduler, etc.) |
| `processors.tf` | Placeholder for processor job infra |
| `indicators.tf` | Placeholder for indicator job infra |
| `publishers.tf` | Placeholder for publisher job infra |
| `backend.tf` | GCS backend |
| `secrets.tf` | Secret Manager resources |
| `variables.tf` | All variables (including `data_providers`, `silver_series`, `silver_indicators`) |

---

# DATA ARCHITECTURE
## MEDALLION + LANDING ZONE

To ensure absolute auditability for high-stakes policy decisions, the system maintains an **Indefinite Retention** policy across all layers. This allows for a "Perfect Trace" from final scores back to the original, byte-for-byte API payloads used to generate the signals.

| Layer | Type | Retention | Responsibility | Primary Format |
| :--- | :--- | :--- | :--- | :--- |
| **landing-zone** | Archive | Indefinite | The Evidence Locker. Original, bit-for-bit API payloads (ZIP, XML, JSON) exactly as delivered. | Raw Source |
| **bronze** | System of Record | Indefinite | Structured History. Uniform, queryable snapshots. Schema-on-read enabled via BigLake. | Parquet / GCS |
| **silver** | Analytical Core | Indefinite | The Workbench. Cleaned, stationarized, and time-aligned features (Smoothing, Log-returns, Z-scores). | PostgreSQL |
| **gold** | Decision Layer | Indefinite | Inference Engine. Probabilistic fragility scores and latent regime classifications. | PostgreSQL / Views |

---

# INTEGRITY AND TRACEABILITY

Because financial stability decisions require high-fidelity justification, the architecture enforces a **Deterministic Lineage Chain**:

1. **Immutable Hashing:** Every file entering the **Landing Zone** is assigned a `SHA-256` hash immediately upon arrival, which will later be linked by a Merkle DAG
2. **Lineage Propagation:** This hash is carried as a `source_file_hash` metadata column through the **Bronze** and **Silver** layers.
3. **Point-in-Time Audit:** Any specific risk score in the **Gold** layer can be traced back to the exact byte-for-byte source file used to generate it, protecting against "silent" upstream data revisions by providers (e.g., FRED).

# USING THE TIERS
Keep Bronze as the canonical, replayable truth (raw + normalized-enough-to-read), and use Silver for computed outputs (features + analysis). Gold is only for the final dashboard tables.

## LANDING ZONE (IMMUTABLE)

Original files exactly as received (CSV/JSON/etc.) TO PROVIDE auditability + easy reprocessing + provenance anchor.

Rules: never mutate; retention/immutability enabled.

## BRONZE (CANONICAL DATA SETS BY PROVIDER)

* What it is: Parquet in GCS, partitioned Hive-style (key=value/) for query pruning.

* Contains: data in the provider’s “natural schema,” but with mechanical standardization so it’s reliably queryable (types stable, consistent partition keys).
* Purpose: “source of truth” for internal processing. Rebuild everything from here.
* Access pattern: BigQuery external tables (BigLake) for fast SQL reads by processors.

### Example paths:
* provider=fred/series=STLFSI3/frequency=Monthly/issued_date=.../ingest_date=.../file.parquet
* provider=massive/series=us_stocks_sip/frequency=Daily/issued_date=.../ingest_date=.../file.parquet

## SILVER (COMPUTED)

Silver is where you add value. It’s still in GCS as Parquet (lakehouse style), but now it’s domain-shaped, not provider-shaped.

### Silver Features
* What it is: derived, reusable metrics (e.g., SMA50/SMA200, returns, rolling vol).
* Input: Bronze external tables (or Bronze parquet) filtered by series/date partitions.
* Output: Parquet partitions keyed by the analysis grain (e.g., trade_date=YYYY-MM-DD, series=...).

### Silver Analysis
* What it is: interpretation / modeling outputs (signals, regimes, risk scores).
* Input: Silver Features (and sometimes directly Bronze).
* Output: Parquet, usually versioned (e.g., model_version=v3/ or signal_version=v2/) so you can reproduce results.

## GOLD (DASHBOARD-READY)
What it is: small, curated tables optimized for the dashboard.
* Store: Postgres (fast reads, indexes, stable schema).
* Input: Silver (features + analysis).
* Purpose: the dashboard never queries Bronze/Silver directly; it hits Gold.

## DEVELOPER WORKFLOW

* Ingestor: raw → landing zone → bronze parquet (hive partitions)
* Feature processor: bronze → silver_features parquet
* Analysis processor: silver_features → silver_analysis parquet
* Publisher: silver → gold tables in Postgres

Bronze = truth, Silver = compute, Gold = serve.