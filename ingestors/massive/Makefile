ADC=~/.config/gcloud/application_default_credentials.json
TAG=massive_ingestor
VERSION=latest
RUNDATE=`date "+%Y%m%d%H%M%S"`

build:
	docker build -t$(TAG):$(VERSION) -t$(TAG):$(RUNDATE) .
# 	docker build -t$(TAG):$(VERSION) --no-cache .

run:
	docker run -it \
		--env-file ../../.env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		-t $(TAG):$(VERSION) 


liverun:
	docker run -it \
		--env-file ../../.env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		-t $(TAG):$(VERSION) \
		uv run main.py

drop:
	docker rmi $(TAG):$(VERSION)
	docker images
