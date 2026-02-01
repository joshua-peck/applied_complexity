ENV=dev
PROJECT_ID=macrocontext
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

plan:
	terraform plan -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)"

apply:
	terraform apply -var="project_id=$(PROJECT_ID)" -var="env=$(ENV)"

auth:
	gcloud auth login
	gcloud auth application-default login
