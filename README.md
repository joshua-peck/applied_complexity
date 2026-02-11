
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
