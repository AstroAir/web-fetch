# Development Guide

This document provides comprehensive information for developers working on the web-fetch library, including setup instructions, testing procedures, and contribution guidelines.

## Table of Contents

- [Development Setup](#development-setup)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Contributing Guidelines](#contributing-guidelines)
- [Release Process](#release-process)
- [Architecture Overview](#architecture-overview)

## Development Setup

### Prerequisites

- **Python 3.11+** (required for modern async features and pattern matching)
- **Git** for version control
- **Make** for build automation (optional but recommended)
- **Docker** for integration testing (optional)

### Environment Setup

1. **Clone the repository:**

```bash
git clone https://github.com/web-fetch/web-fetch.git
cd web-fetch
```

2. **Create and activate virtual environment:**

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n web-fetch python=3.11
conda activate web-fetch
```

3. **Install development dependencies:**

```bash
# Install in development mode with all dependencies
pip install -e ".[all,dev,test]"

# Or using the development script
./scripts/setup-dev.sh
```

4. **Install pre-commit hooks:**

```bash
pre-commit install
```

5. **Verify installation:**

```bash
python -c "import web_fetch; print(web_fetch.__version__)"
pytest --version
black --version
mypy --version
```

### Development Tools Configuration

#### VS Code Setup

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "88"],
    "python.sortImports.args": ["--profile", "black"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests",
        "-v",
        "--tb=short"
    ]
}
```

#### PyCharm Setup

1. Set Python interpreter to `./venv/bin/python`
2. Configure code style to use Black formatting
3. Enable pytest as test runner
4. Configure mypy as external tool

### Environment Variables for Development

Create `.env` file in project root:

```bash
# Development settings
WEB_FETCH_LOG_LEVEL=DEBUG
WEB_FETCH_ENABLE_METRICS=true

# Test API keys (use test/sandbox keys only)
FIRECRAWL_API_KEY=fc-test-key
SPIDER_API_KEY=test-spider-key
TAVILY_API_KEY=tvly-test-key

# Test FTP server (for integration tests)
TEST_FTP_HOST=localhost
TEST_FTP_USERNAME=testuser
TEST_FTP_PASSWORD=testpass

# Redis for cache testing
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=15  # Use separate DB for tests
```

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration and fixtures
├── test_fetcher.py            # Core HTTP fetcher tests
├── test_fetcher_comprehensive.py  # Comprehensive integration tests
├── test_ftp.py                # FTP functionality tests
├── test_models.py             # Data model tests
├── test_streaming.py          # Streaming functionality tests
├── test_utils.py              # Utility function tests
├── test_utils_comprehensive.py    # Comprehensive utility tests
├── test_crawlers.py           # Crawler integration tests
├── integration/               # Integration test suites
│   ├── test_real_websites.py
│   ├── test_ftp_servers.py
│   └── test_crawler_apis.py
├── performance/               # Performance benchmarks
│   ├── test_concurrent_requests.py
│   ├── test_memory_usage.py
│   └── test_streaming_performance.py
└── fixtures/                  # Test data and mock responses
    ├── sample_responses/
    ├── test_files/
    └── mock_servers.py
```

### Running Tests

#### Basic Test Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_fetcher.py

# Run specific test function
pytest tests/test_fetcher.py::test_fetch_single_success

# Run tests matching pattern
pytest -k "test_fetch"

# Run tests with coverage
pytest --cov=web_fetch --cov-report=html

# Run only fast tests (skip integration tests)
pytest -m "not integration"

# Run only integration tests
pytest -m integration
```

#### Test Categories

Tests are organized into categories using pytest markers:

- `@pytest.mark.unit` - Fast unit tests (default)
- `@pytest.mark.integration` - Integration tests requiring external services
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.slow` - Slow tests that take >5 seconds

#### Parallel Testing

```bash
# Install pytest-xdist for parallel execution
pip install pytest-xdist

# Run tests in parallel
pytest -n auto  # Use all CPU cores
pytest -n 4     # Use 4 processes
```

### Writing Tests

#### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, patch
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

class TestWebFetcher:
    """Test suite for WebFetcher class."""
    
    @pytest.fixture
    async def fetcher(self):
        """Create a WebFetcher instance for testing."""
        config = FetchConfig(max_concurrent_requests=5)
        async with WebFetcher(config) as fetcher:
            yield fetcher
    
    @pytest.mark.asyncio
    async def test_fetch_single_success(self, fetcher):
        """Test successful single URL fetch."""
        request = FetchRequest(
            url="https://httpbin.org/json",
            content_type=ContentType.JSON
        )
        
        result = await fetcher.fetch_single(request)
        
        assert result.is_success
        assert result.status_code == 200
        assert isinstance(result.content, dict)
        assert result.response_time > 0
    
    @pytest.mark.asyncio
    async def test_fetch_single_timeout(self, fetcher):
        """Test request timeout handling."""
        request = FetchRequest(
            url="https://httpbin.org/delay/10",
            timeout_override=1.0  # 1 second timeout
        )
        
        result = await fetcher.fetch_single(request)
        
        assert not result.is_success
        assert "timeout" in result.error.lower()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_fetch_with_mock(self, mock_get, fetcher):
        """Test with mocked HTTP response."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.read.return_value = b'{"test": "data"}'
        mock_get.return_value.__aenter__.return_value = mock_response
        
        request = FetchRequest(
            url="https://example.com/api",
            content_type=ContentType.JSON
        )
        
        result = await fetcher.fetch_single(request)
        
        assert result.is_success
        assert result.content == {"test": "data"}
        mock_get.assert_called_once()
```

#### Integration Test Example

```python
import pytest
from web_fetch import FTPFetcher, FTPConfig, FTPRequest
from pathlib import Path

class TestFTPIntegration:
    """Integration tests for FTP functionality."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ftp_download_real_server(self):
        """Test FTP download from real server."""
        config = FTPConfig(
            auth_type=FTPAuthType.ANONYMOUS,
            connection_timeout=30.0
        )
        
        async with FTPFetcher(config) as ftp:
            # Test with a known public FTP server
            request = FTPRequest(
                url="ftp://ftp.gnu.org/gnu/README",
                local_path=Path("test_downloads/README")
            )
            
            result = await ftp.download_file(request)
            
            assert result.is_success
            assert result.bytes_downloaded > 0
            assert Path("test_downloads/README").exists()
            
            # Cleanup
            Path("test_downloads/README").unlink()
```

### Test Configuration

#### pytest.ini

```ini
[tool:pytest]
minversion = 7.0
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov=web_fetch
    --cov-branch
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=85
testpaths = tests
markers =
    unit: Fast unit tests
    integration: Integration tests requiring external services
    performance: Performance benchmarks
    slow: Tests that take more than 5 seconds
    network: Tests requiring network access
    ftp: FTP-related tests
    crawler: Crawler API tests
asyncio_mode = auto
filterwarnings =
    error
    ignore::UserWarning
    ignore::DeprecationWarning
```

#### conftest.py

```python
import pytest
import asyncio
from pathlib import Path
from web_fetch import WebFetcher, FetchConfig

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def basic_fetcher():
    """Provide a basic WebFetcher instance."""
    config = FetchConfig(max_concurrent_requests=3)
    async with WebFetcher(config) as fetcher:
        yield fetcher

@pytest.fixture
def temp_download_dir(tmp_path):
    """Provide a temporary directory for downloads."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir

@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Automatically cleanup test files after each test."""
    yield
    # Cleanup logic here
    test_files = Path(".").glob("test_*")
    for file in test_files:
        if file.is_file():
            file.unlink()
```

## Code Quality

### Code Formatting

The project uses **Black** for code formatting:

```bash
# Format all code
black .

# Check formatting without making changes
black --check .

# Format specific files
black web_fetch/ tests/
```

### Import Sorting

Use **isort** for import organization:

```bash
# Sort imports
isort .

# Check import sorting
isort --check-only .

# Sort with Black compatibility
isort --profile black .
```

### Type Checking

Use **mypy** for static type checking:

```bash
# Run type checking
mypy web_fetch/

# Run with strict mode
mypy --strict web_fetch/

# Check specific files
mypy web_fetch/fetcher.py web_fetch/models/
```

### Linting

Use **flake8** for code linting:

```bash
# Run linting
flake8 web_fetch/ tests/

# With specific configuration
flake8 --max-line-length=88 --extend-ignore=E203,W503 web_fetch/
```

### Security Scanning

Use **bandit** for security analysis:

```bash
# Install bandit
pip install bandit

# Run security scan
bandit -r web_fetch/

# Generate report
bandit -r web_fetch/ -f json -o security-report.json
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ["--max-line-length=88", "--extend-ignore=E203,W503"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-aiofiles]
```

### Continuous Integration

#### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[all,dev,test]"
    
    - name: Run pre-commit
      run: pre-commit run --all-files
    
    - name: Run tests
      run: |
        pytest --cov=web_fetch --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

## Contributing Guidelines

### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch** from `develop`
4. **Make your changes** following the coding standards
5. **Add tests** for new functionality
6. **Run the test suite** to ensure everything works
7. **Submit a pull request** with a clear description

### Branch Strategy

- `main` - Stable release branch
- `develop` - Development integration branch
- `feature/feature-name` - Feature development branches
- `bugfix/bug-description` - Bug fix branches
- `hotfix/critical-fix` - Critical production fixes

### Commit Message Format

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:

```
feat(http): add circuit breaker pattern support

Add circuit breaker implementation to prevent cascading failures
when external services are experiencing issues.

Closes #123
```

### Pull Request Guidelines

1. **Title**: Clear, descriptive title
2. **Description**: Detailed description of changes
3. **Testing**: Describe how the changes were tested
4. **Documentation**: Update relevant documentation
5. **Breaking Changes**: Clearly mark any breaking changes

#### Pull Request Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Corresponding changes to documentation made
- [ ] No new warnings introduced
- [ ] Tests added that prove the fix is effective or feature works
```

### Code Review Process

1. **Automated Checks**: All CI checks must pass
2. **Peer Review**: At least one maintainer review required
3. **Testing**: Comprehensive test coverage required
4. **Documentation**: Documentation updates for new features
5. **Performance**: Performance impact assessment for significant changes

## Release Process

### Version Management

The project follows [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes (backward compatible)

### Release Checklist

1. **Update Version**: Update version in `pyproject.toml` and `__init__.py`
2. **Update Changelog**: Add release notes to `CHANGELOG.md`
3. **Run Tests**: Ensure all tests pass
4. **Build Package**: Create distribution packages
5. **Tag Release**: Create git tag with version
6. **Publish**: Upload to PyPI
7. **GitHub Release**: Create GitHub release with notes

### Release Commands

```bash
# Update version (using bump2version)
bump2version patch  # or minor, major

# Build distribution packages
python -m build

# Upload to PyPI (using twine)
twine upload dist/*

# Create git tag
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

## Architecture Overview

### Project Structure

```
web-fetch/
├── web_fetch/                 # Main package
│   ├── __init__.py           # Package exports and version
│   ├── fetcher.py            # Main fetcher interface
│   ├── exceptions.py         # Exception hierarchy
│   ├── models/               # Data models
│   │   ├── __init__.py
│   │   ├── base.py          # Base models and enums
│   │   ├── http.py          # HTTP-specific models
│   │   └── ftp.py           # FTP-specific models
│   ├── src/                  # Core implementation
│   │   ├── __init__.py
│   │   ├── core_fetcher.py  # Main HTTP fetcher
│   │   ├── streaming_fetcher.py  # Streaming functionality
│   │   ├── convenience.py   # Convenience functions
│   │   └── url_utils.py     # URL utilities
│   ├── ftp/                  # FTP functionality
│   │   ├── __init__.py
│   │   ├── fetcher.py       # Main FTP fetcher
│   │   ├── connection.py    # Connection management
│   │   ├── operations.py    # File operations
│   │   ├── streaming.py     # Streaming downloads
│   │   ├── parallel.py      # Parallel downloads
│   │   └── verification.py  # File verification
│   ├── utils/                # Utility modules
│   │   ├── __init__.py
│   │   ├── cache.py         # Caching implementations
│   │   ├── rate_limit.py    # Rate limiting
│   │   ├── circuit_breaker.py  # Circuit breaker pattern
│   │   ├── deduplication.py # Request deduplication
│   │   ├── transformers.py  # Response transformers
│   │   ├── metrics.py       # Metrics collection
│   │   └── validation.py    # Input validation
│   ├── parsers/              # Content parsers
│   │   ├── __init__.py
│   │   ├── content_parser.py # Main parser interface
│   │   ├── pdf_parser.py    # PDF parsing
│   │   ├── image_parser.py  # Image processing
│   │   ├── feed_parser.py   # RSS/Atom feeds
│   │   └── csv_parser.py    # CSV parsing
│   ├── crawlers/             # Crawler integrations
│   │   ├── __init__.py
│   │   ├── base.py          # Base crawler classes
│   │   ├── manager.py       # Crawler management
│   │   ├── firecrawl_crawler.py  # Firecrawl integration
│   │   ├── spider_crawler.py     # Spider.cloud integration
│   │   └── tavily_crawler.py     # Tavily integration
│   └── cli/                  # Command-line interface
│       ├── __init__.py
│       └── main.py          # CLI implementation
├── tests/                    # Test suite
├── docs/                     # Documentation
├── examples/                 # Usage examples
├── scripts/                  # Development scripts
├── pyproject.toml           # Project configuration
├── README.md                # Project overview
├── CHANGELOG.md             # Release notes
├── CONTRIBUTING.md          # Contribution guidelines
└── LICENSE                  # License file
```

### Design Principles

1. **Async First**: Built for async/await from the ground up
2. **Type Safety**: Comprehensive type hints and Pydantic validation
3. **Modularity**: Clean separation of concerns and pluggable components
4. **Performance**: Optimized for high-throughput concurrent operations
5. **Reliability**: Comprehensive error handling and resilience patterns
6. **Extensibility**: Easy to extend with new protocols and features
7. **Developer Experience**: Clear APIs and comprehensive documentation

### Key Components

- **Core Fetcher**: Main HTTP client with session management
- **Streaming Fetcher**: Memory-efficient large file handling
- **FTP Module**: Complete FTP client implementation
- **Crawler Integration**: Unified interface for multiple crawler APIs
- **Content Parsers**: Extensible content processing pipeline
- **Utility Layer**: Caching, rate limiting, circuit breakers, metrics
- **CLI Interface**: Command-line tool for common operations

This architecture provides a solid foundation for reliable, high-performance web fetching operations while maintaining clean code organization and extensibility.

```
