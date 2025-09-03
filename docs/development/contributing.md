# Contributing to WebFetch

We welcome contributions to WebFetch! This guide will help you get started with development and contributing to the project.

## Development Setup

### Prerequisites

- **Python 3.11+** (required for modern async features and pattern matching)
- **Git** for version control
- **Make** for build automation (optional but recommended)
- **Docker** for integration testing (optional)

### Environment Setup

1. **Clone the repository:**

```bash
git clone https://github.com/AstroAir/web-fetch.git
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

### Development Tools

The project uses several development tools:

- **pytest** - Testing framework
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Type checking
- **flake8** - Linting
- **pre-commit** - Git hooks for code quality

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=web_fetch --cov-report=html

# Run specific test file
pytest tests/test_fetcher.py

# Run with verbose output
pytest -v

# Run only unit tests (skip integration tests)
pytest -m "not integration"

# Run only integration tests
pytest -m integration
```

### Test Categories

- **Unit tests**: Test individual components and functions
- **Integration tests**: Test with real HTTP requests (marked as `@pytest.mark.integration`)
- **Error scenario tests**: Test various failure modes and error handling

### Writing Tests

When adding new features, please include tests:

```python
import pytest
from web_fetch import fetch_url, ContentType

@pytest.mark.asyncio
async def test_fetch_json():
    """Test fetching JSON content."""
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    assert result.is_success
    assert isinstance(result.content, dict)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api():
    """Integration test with real API."""
    # This test requires internet connection
    result = await fetch_url("https://api.github.com", ContentType.JSON)
    assert result.is_success
```

## Code Quality

### Code Formatting

We use **black** for code formatting:

```bash
# Format all code
black .

# Check formatting without making changes
black --check .
```

### Import Sorting

We use **isort** for import organization:

```bash
# Sort imports
isort .

# Check import sorting
isort --check-only .
```

### Type Checking

We use **mypy** for static type checking:

```bash
# Run type checking
mypy web_fetch

# Run with strict mode
mypy --strict web_fetch
```

### Linting

We use **flake8** for additional linting:

```bash
# Run linting
flake8 web_fetch tests
```

### Pre-commit Hooks

Pre-commit hooks automatically run code quality checks:

```bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Contributing Guidelines

### Pull Request Process

1. **Fork the repository** and create a feature branch
2. **Make your changes** with appropriate tests
3. **Ensure all tests pass** and code quality checks succeed
4. **Update documentation** if needed
5. **Submit a pull request** with a clear description

### Branch Naming

Use descriptive branch names:

- `feature/add-oauth-support`
- `bugfix/fix-timeout-handling`
- `docs/update-api-reference`
- `refactor/improve-error-handling`

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Examples:
- `feat(auth): add OAuth 2.0 support`
- `fix(http): handle connection timeouts properly`
- `docs(api): update fetch_url documentation`
- `test(batch): add tests for batch operations`

### Code Style Guidelines

1. **Follow PEP 8** style guidelines
2. **Use type hints** for all function parameters and return values
3. **Write docstrings** for all public functions and classes
4. **Keep functions focused** and single-purpose
5. **Use meaningful variable names**
6. **Add comments** for complex logic

### Documentation

When adding new features:

1. **Update docstrings** with examples
2. **Add to API documentation** if public API
3. **Update README** if user-facing feature
4. **Add examples** to demonstrate usage

## Architecture Overview

### Project Structure

```
web-fetch/
├── web_fetch/                    # Main package
│   ├── __init__.py              # Package exports
│   ├── fetcher.py               # Main fetcher interface
│   ├── exceptions.py            # Exception hierarchy
│   ├── models/                  # Data models
│   ├── core/                    # Core HTTP implementation
│   ├── ftp/                     # FTP functionality
│   ├── utils/                   # Utility modules
│   ├── parsers/                 # Content parsers
│   ├── crawlers/                # Crawler integrations
│   └── cli/                     # Command-line interface
├── tests/                       # Test suite
├── docs/                        # Documentation
├── examples/                    # Usage examples
└── scripts/                     # Development scripts
```

### Design Principles

1. **Async-first**: All I/O operations are asynchronous
2. **Type safety**: Comprehensive type hints and validation
3. **Modular design**: Clear separation of concerns
4. **Error handling**: Comprehensive error hierarchy
5. **Performance**: Optimized for high-throughput scenarios
6. **Extensibility**: Plugin architecture for parsers and crawlers

### Key Components

- **WebFetcher**: Main HTTP client with connection pooling
- **StreamingWebFetcher**: Streaming downloads for large files
- **Content Parsers**: Pluggable content parsing system
- **Crawler Integrations**: Multiple web scraping service integrations
- **Configuration System**: Flexible configuration with validation

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with release notes
3. **Run full test suite** including integration tests
4. **Update documentation** if needed
5. **Create release tag** and GitHub release
6. **Publish to PyPI** (automated via CI/CD)

## Getting Help

### Development Questions

- **GitHub Discussions** - For general questions and ideas
- **GitHub Issues** - For bug reports and feature requests
- **Code Review** - Submit PRs for feedback

### Resources

- **[API Documentation](../api/core.md)** - Complete API reference
- **[Examples](../examples/basic.md)** - Usage examples
- **[Architecture Guide](architecture.md)** - Detailed architecture overview

## Recognition

Contributors are recognized in:

- **CONTRIBUTORS.md** file
- **GitHub contributors** page
- **Release notes** for significant contributions

Thank you for contributing to WebFetch! 🚀
