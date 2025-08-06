# Comprehensive Examples Guide

This guide provides an overview of all the examples and documentation available for the web-fetch library, organized by use case and complexity level.

## 📚 Documentation Structure

### Core Documentation
- **[README.md](../README.md)** - Main project documentation and quick start
- **[EXAMPLES.md](EXAMPLES.md)** - Basic usage examples and common patterns
- **[ADVANCED_EXAMPLES.md](ADVANCED_EXAMPLES.md)** - Advanced features and complex scenarios

### Specialized Guides
- **[CLI_EXAMPLES.md](CLI_EXAMPLES.md)** - Complete command-line interface usage
- **[PARSER_EXAMPLES.md](PARSER_EXAMPLES.md)** - Content parsing and data extraction
- **[CONFIGURATION_EXAMPLES.md](CONFIGURATION_EXAMPLES.md)** - Configuration patterns and best practices
- **[ERROR_HANDLING_EXAMPLES.md](ERROR_HANDLING_EXAMPLES.md)** - Error handling and resilience patterns

## 🚀 Getting Started Examples

### For Beginners
Start with these examples to understand the basics:

1. **[Basic Usage](../examples/basic_usage.py)**
   ```python
   from web_fetch import fetch_url, ContentType
   
   result = await fetch_url("https://api.example.com/data", ContentType.JSON)
   if result.is_success:
       print(result.content)
   ```

2. **[Simple Configuration](../examples/configuration_examples.py)**
   ```python
   config = FetchConfig(
       total_timeout=30.0,
       max_retries=3,
       max_concurrent_requests=10
   )
   ```

3. **[Basic Error Handling](../examples/error_handling_examples.py)**
   ```python
   try:
       result = await fetch_url(url)
   except TimeoutError:
       print("Request timed out")
   except HTTPError as e:
       print(f"HTTP error: {e.status_code}")
   ```

### For Intermediate Users
Once comfortable with basics, explore these patterns:

1. **[Batch Processing](../examples/advanced_usage.py)**
   - Process multiple URLs concurrently
   - Handle mixed success/failure scenarios
   - Optimize for throughput

2. **[Content Parsing](../examples/parser_examples.py)**
   - JSON, HTML, CSV, and other formats
   - Error handling for parsing failures
   - Custom content processing

3. **[Configuration Management](../examples/configuration_examples.py)**
   - Environment-based configuration
   - Profile-based settings
   - Configuration validation

### For Advanced Users
For complex applications and production use:

1. **[Real-World Integration](../examples/real_world_integration_examples.py)**
   - API integration patterns
   - Web scraping workflows
   - Data pipeline integration
   - Microservice communication

2. **[Performance Optimization](../examples/performance_optimization_examples.py)**
   - Connection pooling
   - Memory management
   - Caching strategies
   - Rate limiting

3. **[Testing Strategies](../examples/testing_examples.py)**
   - Unit testing with mocks
   - Integration testing
   - Performance testing
   - Error scenario testing

## 🎯 Use Case Examples

### API Integration
**Files:** `real_world_integration_examples.py`, `advanced_usage.py`

```python
# REST API operations
async def api_integration():
    async with WebFetcher(config) as fetcher:
        # GET
        result = await fetcher.fetch_single(
            FetchRequest(url="/api/users/1", content_type=ContentType.JSON)
        )
        
        # POST
        result = await fetcher.fetch_single(
            FetchRequest(
                url="/api/users",
                method="POST",
                data=json.dumps(user_data),
                headers={"Content-Type": "application/json"}
            )
        )
```

### Web Scraping
**Files:** `real_world_integration_examples.py`, `parser_examples.py`

```python
# Scrape with rate limiting and error handling
class WebScraper:
    def __init__(self):
        self.config = FetchConfig(
            max_concurrent_requests=3,
            rate_limit_config=RateLimitConfig(requests_per_second=2.0)
        )
    
    async def scrape_pages(self, urls):
        return await fetch_urls(urls, ContentType.HTML, self.config)
```

### Data Pipeline
**Files:** `real_world_integration_examples.py`, `performance_optimization_examples.py`

```python
# ETL pipeline with web-fetch
class DataPipeline:
    async def extract(self):
        # Extract from multiple sources
        pass
    
    async def transform(self, data):
        # Transform extracted data
        pass
    
    async def load(self, data):
        # Load to destination
        pass
```

### Microservices
**Files:** `real_world_integration_examples.py`, `error_handling_examples.py`

```python
# Service-to-service communication
class ServiceClient:
    async def health_check(self):
        # Check service health
        pass
    
    async def call_service(self, endpoint, data):
        # Make service call with retries
        pass
```

## 🛠️ Feature Examples

### Command Line Interface
**Files:** `cli_comprehensive_examples.py`, `CLI_EXAMPLES.md`

```bash
# Basic usage
web-fetch https://api.example.com/data

# Batch processing
web-fetch --batch urls.txt --concurrent 5

# With caching
web-fetch --cache --cache-ttl 300 https://api.example.com/data

# Streaming download
web-fetch --stream --progress -o file.zip https://example.com/file.zip
```

### Content Parsing
**Files:** `parser_examples.py`, `PARSER_EXAMPLES.md`

```python
# Different content types
json_result = await fetch_url(url, ContentType.JSON)
html_result = await fetch_url(url, ContentType.HTML)
text_result = await fetch_url(url, ContentType.TEXT)
raw_result = await fetch_url(url, ContentType.RAW)

# Structured data extraction
if html_result.is_success:
    page_data = html_result.content
    links = page_data.get('links', [])
    images = page_data.get('images', [])
```

### Configuration Patterns
**Files:** `configuration_examples.py`, `CONFIGURATION_EXAMPLES.md`

```python
# Environment-based configuration
config = create_config_from_env()

# Profile-based configuration
config = config_manager.get_config('production')

# Configuration validation
validator = ConfigValidator()
if validator.validate_config(config):
    print("Configuration is valid")
```

### Error Handling
**Files:** `error_handling_examples.py`, `ERROR_HANDLING_EXAMPLES.md`

```python
# Specific exception handling
try:
    result = await fetch_url(url)
except TimeoutError:
    # Handle timeout
    pass
except RateLimitError:
    # Handle rate limiting
    pass
except ServerError as e:
    # Handle server errors
    if e.status_code >= 500:
        # Retry logic
        pass
```

### Performance Optimization
**Files:** `performance_optimization_examples.py`

```python
# Connection pooling
async with WebFetcher(config) as fetcher:
    # Reuse connections for multiple requests
    results = await fetch_urls(urls, ContentType.JSON, config)

# Memory optimization
config = FetchConfig(
    max_response_size=1024*1024,  # 1MB limit
    max_concurrent_requests=5
)

# Caching
cache_config = CacheConfig(ttl_seconds=300, max_size=100)
```

## 🧪 Testing Examples

### Unit Testing
**Files:** `testing_examples.py`

```python
@patch('web_fetch.WebFetcher.fetch_single')
async def test_mocked_response(mock_fetch):
    mock_fetch.return_value = FetchResult(...)
    # Test your code
```

### Integration Testing
**Files:** `testing_examples.py`

```python
async def test_real_api():
    result = await fetch_url("https://httpbin.org/get", ContentType.JSON)
    assert result.is_success
    assert result.status_code == 200
```

### Performance Testing
**Files:** `testing_examples.py`, `performance_optimization_examples.py`

```python
async def test_concurrent_performance():
    start_time = time.time()
    results = await fetch_urls(urls, ContentType.JSON, config)
    duration = time.time() - start_time
    
    assert duration < expected_max_time
    assert results.success_rate > 0.95
```

## 📊 Performance Guidelines

### Concurrency Recommendations
- **Small APIs**: 3-5 concurrent requests
- **Large APIs**: 10-20 concurrent requests
- **Web scraping**: 2-5 concurrent requests (be respectful)
- **Internal services**: 20-50 concurrent requests

### Timeout Guidelines
- **Fast APIs**: 5-10 seconds total timeout
- **Slow APIs**: 30-60 seconds total timeout
- **File downloads**: 300+ seconds total timeout
- **Connect timeout**: Usually 5-15 seconds

### Memory Management
- **Large files**: Use streaming or response size limits
- **Batch processing**: Process in chunks of 10-50 URLs
- **Long-running**: Monitor memory usage and implement cleanup

### Caching Strategy
- **Static content**: Long TTL (hours/days)
- **Dynamic content**: Short TTL (minutes)
- **API responses**: Medium TTL (5-30 minutes)
- **Error responses**: Very short TTL (30 seconds)

## 🔧 Troubleshooting Guide

### Common Issues and Solutions

1. **Timeout Errors**
   - Increase timeout values
   - Check network connectivity
   - Verify target server performance

2. **Rate Limiting**
   - Implement rate limiting configuration
   - Add delays between requests
   - Use exponential backoff

3. **Memory Issues**
   - Limit response sizes
   - Process in smaller batches
   - Use streaming for large files

4. **SSL/TLS Errors**
   - Update certificates
   - Configure SSL verification properly
   - Handle self-signed certificates in development

5. **Parsing Errors**
   - Validate content type before parsing
   - Handle empty responses
   - Implement fallback parsing strategies

## 📖 Additional Resources

### Example Files Quick Reference
- `basic_usage.py` - Simple examples for beginners
- `advanced_usage.py` - Complex patterns and features
- `cli_comprehensive_examples.py` - Complete CLI usage
- `parser_examples.py` - Content parsing and extraction
- `configuration_examples.py` - Configuration patterns
- `error_handling_examples.py` - Error handling strategies
- `real_world_integration_examples.py` - Production use cases
- `testing_examples.py` - Testing strategies
- `performance_optimization_examples.py` - Performance tuning
- `streaming_examples.py` - Streaming and downloads
- `crawler_examples.py` - Web crawler integration

### Documentation Files
- `CLI_EXAMPLES.md` - Command-line usage guide
- `PARSER_EXAMPLES.md` - Content parsing guide
- `CONFIGURATION_EXAMPLES.md` - Configuration guide
- `ERROR_HANDLING_EXAMPLES.md` - Error handling guide

### Running Examples
```bash
# Run individual examples
python examples/basic_usage.py
python examples/advanced_usage.py
python examples/performance_optimization_examples.py

# Run CLI examples
python examples/cli_comprehensive_examples.py

# Run tests
python examples/testing_examples.py
python -m pytest examples/testing_examples.py
```

This comprehensive guide should help you find the right examples for your specific use case and skill level. Start with the basics and gradually work your way up to more advanced patterns as needed.
