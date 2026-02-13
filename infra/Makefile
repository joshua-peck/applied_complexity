ENV=dev
PROJECT_ID=macrocontext
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

ifndef GOLD_POSTGRES_PASSWORD
    $(error GOLD_POSTGRES_PASSWORD is not defined! Please set it.)
endif

ifndef METABASE_DB_PASSWORD
    $(error METABASE_DB_PASSWORD is not defined! Please set it.)
endif

.SILENT: refresh plan apply

PIPELINE_IMAGE_TAG ?= latest

refresh:
	terraform refresh  -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)" -var="metabase_db_password=$(METABASE_DB_PASSWORD)" -var="pipeline_image_tag=$(PIPELINE_IMAGE_TAG)"

plan:
	terraform plan -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)" -var="metabase_db_password=$(METABASE_DB_PASSWORD)" -var="pipeline_image_tag=$(PIPELINE_IMAGE_TAG)"

apply:
	terraform apply -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)" -var="metabase_db_password=$(METABASE_DB_PASSWORD)" -var="pipeline_image_tag=$(PIPELINE_IMAGE_TAG)"

auth:
	gcloud auth login
	gcloud auth application-default login
