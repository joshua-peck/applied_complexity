
# INITIALIZE PROJECT
From `infra/modules/medallion_core`

    # Log in to your gcloud account
    $ gcloud auth application-default login

    # Initialize the cloud env
    $ terraform init

    # Inspect the changes before deploying
    $ terraform plan \
      -var="appliedcomplexity" \
      -var="env=dev"

    # Deploy the changes
    $ terraform apply \
      -var="appliedcomplexity" \
      -var="env=dev"
