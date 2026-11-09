.PHONY: up down logs test eval lint demo

up:      ## Build and start the API and Qdrant
	docker compose up --build -d

down:    ## Stop everything (data is kept in the volume)
	docker compose down

logs:    ## Follow the API logs
	docker compose logs -f api

test:    ## Unit tests: offline, no API key needed
	python -m pytest

eval:    ## Benchmark evaluation against the real LLM (needs Qdrant + API key)
	python -m pytest tests/eval -m eval -v --tb=short

lint:    ## Static checks
	python -m ruff check app tests

demo:    ## Send the 5 benchmark questions to the running API
	python -m scripts.demo