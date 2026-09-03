.PHONY: help infra seed api api-console smoke test ui down clean

help:
	@echo "Targets:"
	@echo "  infra        Start the docker compose stack (app infra + metrics profile), wait for healthy"
	@echo "  seed         Seed Oracle with the CMS and DAKSH schemas"
	@echo "  api          Run the backend on the host (uvicorn --reload, port 8000)"
	@echo "  api-console  Same as 'api', with OTel traces printed to stdout instead of exported"
	@echo "  smoke        Run the end-to-end smoke test against a running API"
	@echo "  test         Run the backend test suite (OTel disabled)"
	@echo "  ui           Run the frontend dev server (frontend_new, npm run dev)"
	@echo "  down         Stop the docker compose stack, keep volumes"
	@echo "  clean        Stop the stack AND DELETE VOLUMES -- destroys the Oracle volume,"
	@echo "               forcing a 3-5 minute re-init on the next 'make infra'"

infra:
	docker compose --profile metrics up -d --wait

seed:
	cd backend && uv run python scripts/seed_oracle.py

api:
	cd backend && uv run uvicorn src.main:app --reload --port 8000

api-console:
	cd backend && OTEL_TRACES_EXPORTER=console uv run uvicorn src.main:app --reload --port 8000

smoke:
	cd backend && uv run python scripts/smoke_e2e.py

test:
	cd backend && OTEL_SDK_DISABLED=true uv run pytest

ui:
	cd frontend_new && npm run dev

down:
	docker compose down

clean:
	docker compose down -v
