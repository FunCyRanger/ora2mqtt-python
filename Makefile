.PHONY: help test test-integration test-system test-cov lint format clean

help:
	@echo "Available targets:"
	@echo "  test           - Run all tests"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-system    - Run system tests only"
	@echo "  test-cov      - Run tests with coverage"
	@echo "  lint          - Run linter"
	@echo "  format        - Format code"
	@echo "  clean         - Clean up"

test:
	pytest

test-integration:
	pytest -m integration

test-system:
	pytest -m system

test-cov:
	pytest --cov=custom_components.ora --cov-report=html --cov-report=term

lint:
	ruff check custom_components/ora tests

format:
	ruff format custom_components/ora tests

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete