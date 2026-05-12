.PHONY: install dev run test lint format docker up down clean setup resetdb

install:
	uv sync

dev:
	PYTHONPATH=app uv run uvicorn app.main:app --reload --port 8011

run:
	PYTHONPATH=app uv run uvicorn app.main:app --host 0.0.0.0 --port 8011

test:
	uv run pytest -x --tb=short -q --cov=app --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ty check

format:
	uv run ruff format . && uv run ruff check --fix .

docker:
	docker build -t fastapi-telegram-base .

up:
	docker compose up -d --build

down:
	docker compose down

setup:
	bash scripts/setup.sh

validate:
	bash scripts/validate.sh

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov .ruff_cache

resetdb:
	docker compose down -v postgres
	docker compose up postgres -d --wait
	@docker compose ps --format '{{.Service}}' | grep -q app && docker compose restart app || true

deploy:
	fastapi deploy
