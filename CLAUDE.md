# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation & Setup
- `make install-dev` - Install with development dependencies
- `make dev-setup` - Install dev dependencies and set up pre-commit hooks
- `pip install -e ".[test,dev]"` - Direct pip installation with dev extras

### Testing
- `make test` - Run all tests
- `make test-unit` - Run unit tests only (marked with `@pytest.mark.unit`)
- `make test-integration` - Run integration tests only (marked with `@pytest.mark.integration`)
- `make test-fast` - Run fast tests (exclude slow and integration tests)
- `make test-coverage` - Run tests with coverage report (requires 80% minimum coverage)
- `pytest tests/test_fetcher.py` - Run specific test file
- `pytest -m "unit"` - Run unit tests
- `pytest -m "integration"` - Run integration tests (requires network)
- `pytest -m "not slow"` - Exclude slow tests

### Code Quality
- `make lint` - Run all linting checks (flake8, black --check, isort --check)
- `make format` - Format code (black, isort)
- `make type-check` - Run mypy type checking
- `make check` - Run lint, type-check, and fast tests
- `make ci` - Full CI pipeline (lint, type-check, coverage tests)

### CLI Usage
- `web-fetch https://example.com` - Basic URL fetch
- `python -m web_fetch.cli` - Alternative CLI invocation
- `main.py` - Demo script showing library features

### Build & Release
- `make build` - Build package (cleans first)
- `make clean` - Remove build artifacts
- `make release-check` - Verify package is ready for release

## Architecture Overview

### Core Structure
The web-fetch library is organized into several key modules:

- **`web_fetch/src/`** - Core HTTP functionality
  - `core_fetcher.py` - Main async HTTP client with aiohttp
  - `streaming_fetcher.py` - Large file streaming capabilities
  - `convenience.py` - High-level convenience functions
  - `url_utils.py` - URL validation and normalization

- **`web_fetch/models/`** - Pydantic data models
  - `base.py` - Base models and enums (ContentType, RetryStrategy)
  - `http.py` - HTTP-specific models (FetchConfig, FetchRequest, FetchResult)
  - `ftp.py` - FTP-specific models

- **`web_fetch/utils/`** - Utility components
  - `cache.py` - Response caching with TTL
  - `rate_limit.py` - Rate limiting with token bucket
  - `circuit_breaker.py` - Circuit breaker pattern
  - `deduplication.py` - Request deduplication
  - `metrics.py` - Performance metrics collection

- **`web_fetch/parsers/`** - Content parsing
  - `content_parser.py` - Main parser interface
  - Specialized parsers for PDF, images, RSS feeds, CSV

- **`web_fetch/ftp/`** - FTP functionality
  - Complete async FTP client with parallel downloads

- **`web_fetch/crawlers/`** - Third-party crawler integrations
  - Firecrawl, Spider.cloud, Tavily integrations

- **`web_fetch/cli/`** - Command-line interface

### Key Design Patterns
- **Async/await throughout** - All operations are async for performance
- **Context managers** - Proper resource cleanup with `async with`
- **Pydantic models** - Type-safe configuration and data validation
- **Error hierarchy** - Structured exception handling from `WebFetchError`
- **Streaming support** - Memory-efficient handling of large files
- **Circuit breakers** - Resilience patterns for external services

### Entry Points
- Primary API: `WebFetcher` and `StreamingWebFetcher` classes
- Convenience functions: `fetch_url()`, `fetch_urls()`, `download_file()`
- CLI: `web-fetch` command or `python -m web_fetch.cli`

## Development Notes

### Testing Strategy
- Unit tests for individual components (no network calls)
- Integration tests for real HTTP requests (marked appropriately)
- Performance tests for benchmarking
- Test markers: `unit`, `integration`, `slow`, `ftp`, `http`, `cli`, `performance`

### Code Style
- Python 3.11+ features used throughout
- Black formatting (88 char line length)
- isort for import organization
- Type hints with mypy enforcement
- Google-style docstrings (pydocstyle)
- Pre-commit hooks enforce quality standards

### Dependencies
- Core: aiohttp, pydantic, beautifulsoup4, aiofiles
- Optional parsers: PyPDF2, Pillow, feedparser, pandas
- Dev tools: pytest, black, isort, mypy, flake8
- Crawlers: firecrawl-py, tavily-python (optional extras)

### Performance Considerations
- Connection pooling via aiohttp sessions
- Configurable concurrency limits
- Memory-efficient streaming for large files
- Response size limits to prevent memory issues
- Caching and rate limiting built-in