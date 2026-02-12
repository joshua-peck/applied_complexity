# PIPELINE CLI (Unified Category-Module)

Single `uv` workspace with Click CLI. Run from project root:

```bash
# Sync dependencies
uv sync

# Discover commands
uv run python mc.py --help
uv run python mc.py ingestors --help   # fred, massive, backfill_history
uv run python mc.py processors --help # stock_features_daily
uv run python mc.py indicators --help # spx_gold_daily
uv run python mc.py publishers --help # spx_gold_trend

# Run a script
uv run python mc.py ingestors fred
uv run python mc.py ingestors massive --report-date 2026-01-15
uv run python mc.py processors stock_features_daily
uv run python mc.py indicators spx_gold_daily
uv run python mc.py publishers spx_gold_trend
```

**Docker (multi-stage):**

```bash
make build-ingestors    # pipeline-ingestors:latest
make build-processors  # pipeline-processors:latest
make build-indicators  # pipeline-indicators:latest
make build-publishers  # pipeline-publishers:latest

make run-massive       # Run massive ingestor container
```

---

# INITIALIZE PROJECT
From `infra/`

    # Log in to your gcloud account
    $ gcloud auth application-default login # or `make auth`

    # Initialize the cloud env
    $ terraform init

    # Inspect the changes before deploying
    $ terraform plan \
      -var="macrocontext" \
      -var="env=dev"

    # Deploy the changes
    $ terraform apply \
      -var="macrocontext" \
      -var="env=dev"

# MANAGE SECRETS
    $ echo -n "YOUR_ACTUAL_FRED_API_KEY" | \
      gcloud secrets versions add FRED_API_KEY --data-file=- --project macrocontext    
    $ echo -n "RANDOMPASSWORD" | \
      gcloud secrets versions add GOLD_POSTGRES_PASSWORD --data-file=- --project macrocontext
    $ echo -n "RANDOMPASSWORD" | \
      gcloud secrets versions add METABASE_DB_PASSWORD --data-file=- --project macrocontext

# DEPENDENCIES
  Make sure to install Google Cloud Auth Proxy for Testing Locally...
  https://docs.cloud.google.com/sql/docs/mysql/connect-instance-auth-proxy

  $ ./cloud-sql-proxy DB_INSTANCE_CONNECTION_NAME
