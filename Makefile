.PHONY: help setup test lint format clean docker-up docker-down run

help:
	@echo "Available commands:"
	@echo "  make setup        - Set up development environment"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean up generated files"
	@echo "  make docker-up    - Start Docker services"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make run          - Run the trading system"

setup:
	@./scripts/setup.sh

test:
	@pytest tests/ -v --cov=src --cov-report=term-missing

test-watch:
	@ptw tests/ -- -v

lint:
	@echo "Running linters..."
	@black --check src tests
	@isort --check-only src tests
	@flake8 src tests
	@mypy src
	@bandit -r src

format:
	@echo "Formatting code..."
	@black src tests
	@isort src tests

clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name "*.coverage" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@rm -rf htmlcov/
	@rm -rf dist/
	@rm -rf build/

docker-up:
	@docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@docker-compose ps

docker-down:
	@docker-compose down

docker-logs:
	@docker-compose logs -f

run:
	@python -m src.main

run-discovery:
	@python -m src.main --mode discovery

run-selection:
	@python -m src.main --mode selection

run-trading:
	@python -m src.main --mode trading

db-upgrade:
	@alembic upgrade head

db-downgrade:
	@alembic downgrade -1

db-history:
	@alembic history

db-current:
	@alembic current

pre-commit:
	@pre-commit run --all-files