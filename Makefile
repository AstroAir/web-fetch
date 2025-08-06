.PHONY: help install install-dev test test-unit test-integration test-coverage lint format type-check clean build docs

# Default target
help:
	@echo "Available targets:"
	@echo "  install          Install the package"
	@echo "  install-dev      Install with development dependencies"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black and isort"
	@echo "  type-check       Run type checking with mypy"
	@echo "  clean            Clean build artifacts"
	@echo "  build            Build the package"
	@echo "  docs             Generate documentation"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[test,dev]"

# Testing targets
test:
	pytest

test-unit:
	pytest -m "unit"

test-integration:
	pytest -m "integration"

test-coverage:
	pytest --cov=web_fetch --cov-report=html --cov-report=term-missing

test-fast:
	pytest -m "not slow and not integration"

# Code quality targets
lint:
	flake8 web_fetch tests examples
	black --check web_fetch tests examples
	isort --check-only web_fetch tests examples

format:
	black web_fetch tests examples
	isort web_fetch tests examples

type-check:
	mypy web_fetch

# Development targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

docs:
	@echo "Documentation is available in:"
	@echo "  README.md - Main documentation"
	@echo "  docs/API.md - API reference"
	@echo "  docs/EXAMPLES.md - Usage examples"
	@echo "  CONTRIBUTING.md - Contributing guidelines"

# Development workflow
dev-setup: install-dev
	pre-commit install

check: lint type-check test-fast

ci: lint type-check test-coverage

# Release targets
release-check: clean lint type-check test
	python -m build
	twine check dist/*

# Docker targets (if needed in the future)
docker-build:
	docker build -t web-fetch .

docker-test:
	docker run --rm web-fetch pytest
