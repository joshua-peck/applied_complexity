ENV=dev
PROJECT_ID=macrocontext
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/legacy_credentials/`gcloud config get account`/adc.json

plan:
	terraform plan -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)"

apply:
	terraform apply -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)"

auth:
	gcloud auth login
	gcloud auth application-default login
