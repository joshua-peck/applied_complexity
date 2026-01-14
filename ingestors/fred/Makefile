ADC=~/.config/gcloud/application_default_credentials.json
TAG=fred_ingestor
VERSION=latest

build:
	docker build -t$(TAG):$(VERSION) --no-cache .

run:
	docker run -it \
  		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
  		-v ${ADC}:/tmp/keys/creds.json:ro \
  		-e LANDING_BUCKET="your-dev-landing-bucket" \
  		-e BRONZE_BUCKET="your-dev-bronze-bucket" \
  		-e FRED_API_KEY="your_actual_key" \
  		$(TAG):$(VERSION)


liverun:
	docker run -it \
		-v $(pwd):/app \ 
		-v ${ADC}:/tmp/keys/creds.json:ro \
 		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		-t$(TAG):$(VERSION) \
 		uv run main.py


drop:
	docker rmi $(TAG):$(VERSION)
	docker images
