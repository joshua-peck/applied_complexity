ADC=~/.config/gcloud/application_default_credentials.json
RUNDATE=`date "+%Y%m%d%H%M%S"`

run:
	docker run --rm -p 3000:3000 \
		--env-file .env \
  		-e MB_DB_TYPE=postgres \
  		-e MB_DB_HOST=host.docker.internal \
  		-e MB_DB_PORT=5432 \
  		-e MB_DB_DBNAME=metabase_app \
  		-e MB_DB_USER=metabase \
  		-e MB_DB_PASS=$(METABASE_PASSWORD) \
		metabase/metabase:latest

