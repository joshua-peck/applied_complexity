ENV=dev
PROJECT_ID=macrocontext
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

ifndef GOLD_POSTGRES_PASSWORD
    $(error GOLD_POSTGRES_PASSWORD is not defined! Please set it.)
endif

refresh:
	terraform refresh  -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)"

plan:
	terraform plan -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)"

apply:
	terraform apply -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)" -var="gold_postgres_password=$(GOLD_POSTGRES_PASSWORD)"

auth:
	gcloud auth login
	gcloud auth application-default login
