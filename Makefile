# Unified pipeline Makefile
# Build category images: make build-ingestors, build-processors, etc.

ADC ?= $(shell echo ~/.config/gcloud/application_default_credentials.json)
TAG ?= pipeline
VERSION ?= latest
REPORT_DATE ?= $(shell date +%Y-%m-%d)
BACKFILL_START ?= 2022-02-12
BACKFILL_END ?= $(shell date +%Y-%m-%d)

# Image tags per category
INGESTOR_TAG = $(TAG)-ingestors
PROCESSOR_TAG = $(TAG)-processors
INDICATOR_TAG = $(TAG)-indicators
PUBLISHER_TAG = $(TAG)-publishers

.PHONY: build-ingestors build-processors build-indicators build-publishers
.PHONY: run-ingestors run-processors run-indicators run-publishers
.PHONY: run-fred run-massive run-stock-features run-spx-gold run-spx-gold-trend
.PHONY: backfill-massive backfill-fred backfill-processors backfill-indicators backfill-publishers backfill-all
.PHONY: help sync

help:
	@echo "Pipeline targets:"
	@echo "  build-ingestors   - Build ingestor image"
	@echo "  build-processors  - Build processor image"
	@echo "  build-indicators - Build indicator image"
	@echo "  build-publishers - Build publisher image"
	@echo "  run-massive      - Run massive ingestor (docker)"
	@echo "  run-fred         - Run fred ingestor (docker)"
	@echo "  run-stock-features - Run stock_features_daily processor (docker)"
	@echo "  run-spx-gold     - Run spx_gold_daily indicator (docker)"
	@echo "  run-spx-gold-trend - Run spx_gold_trend publisher (docker)"
	@echo "  backfill-massive  - Backfill massive ingestor (BACKFILL_START/END)"
	@echo "  backfill-fred     - Backfill fred ingestor (one-shot)"
	@echo "  backfill-processors - Backfill stock_features_daily processor"
	@echo "  backfill-indicators - Backfill spx_gold_daily indicator"
	@echo "  backfill-publishers - Backfill spx_gold_trend publisher"
	@echo "  backfill-all      - Backfill all stages in order"
	@echo "  sync             - uv sync"

sync:
	uv sync

build-ingestors:
	docker build -t $(INGESTOR_TAG):$(VERSION) --target ingestor .

build-processors:
	docker build -t $(PROCESSOR_TAG):$(VERSION) --target processor .

build-indicators:
	docker build -t $(INDICATOR_TAG):$(VERSION) --target indicator .

build-publishers:
	docker build -t $(PUBLISHER_TAG):$(VERSION) --target publisher .

# Run ingestor images (requires .env with credentials)
run-fred:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		$(INGESTOR_TAG):$(VERSION) ingestors fred --report-date $(REPORT_DATE)

run-massive:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		$(INGESTOR_TAG):$(VERSION) ingestors massive --report-date $(REPORT_DATE)

run-stock-features:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		$(PROCESSOR_TAG):$(VERSION) processors stock_features_daily --report-date $(REPORT_DATE)

run-spx-gold:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		$(INDICATOR_TAG):$(VERSION) indicators spx_gold_daily --report-date $(REPORT_DATE)

run-spx-gold-trend:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		-e GOLD_POSTGRES_PASSWORD=$${GOLD_POSTGRES_PASSWORD} \
		$(PUBLISHER_TAG):$(VERSION) publishers spx_gold_trend --report-date $(REPORT_DATE)

# Backfill targets (run at setup). Override BACKFILL_START/BACKFILL_END as needed.
backfill-massive:
	uv run python mc.py backfill --stage ingestors --start $(BACKFILL_START) --end $(BACKFILL_END)

backfill-fred:
	docker run -it \
		--env-file .env \
		-v $(ADC):/tmp/keys/creds.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
		$(INGESTOR_TAG):$(VERSION) ingestors fred

backfill-processors:
	uv run python mc.py backfill --stage processors --start $(BACKFILL_START) --end $(BACKFILL_END)

backfill-indicators:
	uv run python mc.py backfill --stage indicators --start $(BACKFILL_START) --end $(BACKFILL_END)

backfill-publishers:
	uv run python mc.py backfill --stage publishers --start $(BACKFILL_START) --end $(BACKFILL_END)

backfill-all: backfill-massive backfill-fred backfill-processors backfill-indicators backfill-publishers
