# Contributing to Web Fetch

Thank you for your interest in contributing to Web Fetch! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Basic understanding of async/await programming
- Familiarity with AIOHTTP and Pydantic (helpful but not required)

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/web-fetch.git
   cd web-fetch
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Install the package in development mode
   pip install -e ".[test]"
   
   # Or using uv (recommended)
   uv sync --dev
   ```

4. **Run tests to verify setup**
   ```bash
   pytest
   ```

## 🛠️ Development Workflow

### Branch Naming

Use descriptive branch names with prefixes:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test improvements

Example: `feature/add-proxy-support` or `fix/timeout-handling`

### Code Style

We follow Python best practices and use modern Python features:

- **Type hints**: All functions should have proper type annotations
- **Async/await**: Use async/await syntax consistently
- **Docstrings**: Use Google-style docstrings for all public functions
- **Line length**: Maximum 88 characters (Black formatter default)
- **Import order**: Use isort for consistent import ordering

### Testing

- Write tests for all new features and bug fixes
- Maintain or improve test coverage
- Use descriptive test names that explain what is being tested
- Include both unit tests and integration tests where appropriate

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=web_fetch --cov-report=html

# Run specific test file
pytest tests/test_fetcher.py

# Run tests with specific markers
pytest -m "not integration"  # Skip integration tests
```

### Code Quality Tools

We recommend using these tools during development:

```bash
# Format code
black web_fetch/ tests/

# Sort imports
isort web_fetch/ tests/

# Type checking
mypy web_fetch/

# Linting
flake8 web_fetch/ tests/
```

## 📝 Contribution Guidelines

### Pull Request Process

1. **Create an issue first** (for significant changes)
   - Describe the problem or feature request
   - Discuss the approach before implementing

2. **Write clear commit messages**
   ```
   feat: add proxy support for HTTP requests
   
   - Add proxy configuration to FetchConfig
   - Update WebFetcher to handle proxy settings
   - Add tests for proxy functionality
   ```

3. **Keep PRs focused and small**
   - One feature or fix per PR
   - Include tests and documentation updates
   - Update CHANGELOG.md if applicable

4. **Fill out the PR template**
   - Describe what changes were made
   - Link to related issues
   - Include testing instructions

### Code Review

- All PRs require at least one review
- Address feedback promptly and professionally
- Be open to suggestions and improvements
- Ensure CI checks pass before requesting review

## 🧪 Testing Guidelines

### Test Categories

1. **Unit Tests** (`tests/test_*.py`)
   - Test individual functions and classes
   - Mock external dependencies
   - Fast execution

2. **Integration Tests** (marked with `@pytest.mark.integration`)
   - Test with real HTTP requests
   - May be slower and require network access
   - Use httpbin.org for reliable test endpoints

3. **Error Scenario Tests**
   - Test various failure modes
   - Verify proper error handling
   - Test retry logic and timeouts

### Writing Good Tests

```python
import pytest
from web_fetch import fetch_url, ContentType

@pytest.mark.asyncio
async def test_fetch_json_success():
    """Test successful JSON fetching from httpbin."""
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    
    assert result.is_success
    assert result.status_code == 200
    assert isinstance(result.content, dict)
    assert "slideshow" in result.content

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_with_timeout():
    """Test timeout handling with slow endpoint."""
    # This test requires network access
    pass
```

## 📚 Documentation

### Code Documentation

- Use Google-style docstrings for all public functions
- Include type hints for all parameters and return values
- Provide usage examples in docstrings for complex functions

```python
async def fetch_url(
    url: str, 
    content_type: ContentType = ContentType.TEXT,
    config: Optional[FetchConfig] = None
) -> FetchResult:
    """
    Fetch a single URL with the specified content type.
    
    Args:
        url: The URL to fetch
        content_type: How to parse the response content
        config: Optional configuration override
        
    Returns:
        FetchResult containing the response data and metadata
        
    Raises:
        WebFetchError: If the request fails
        
    Example:
        >>> result = await fetch_url("https://api.example.com/data", ContentType.JSON)
        >>> if result.is_success:
        ...     print(result.content)
    """
```

### README Updates

- Update examples if you add new features
- Keep the feature list current
- Update installation instructions if needed

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Environment information**
   - Python version
   - Operating system
   - Package version

2. **Reproduction steps**
   - Minimal code example
   - Expected vs actual behavior
   - Error messages and stack traces

3. **Additional context**
   - Network conditions
   - Target URLs (if safe to share)
   - Configuration used

## 💡 Feature Requests

For new features:

1. **Check existing issues** to avoid duplicates
2. **Describe the use case** and motivation
3. **Propose an API design** if applicable
4. **Consider backward compatibility**

## 🏷️ Release Process

Releases follow semantic versioning (SemVer):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Code Review**: For implementation feedback

## 🙏 Recognition

Contributors will be recognized in:
- CHANGELOG.md for their contributions
- GitHub contributors page
- Special thanks for significant contributions

Thank you for contributing to Web Fetch! 🎉
