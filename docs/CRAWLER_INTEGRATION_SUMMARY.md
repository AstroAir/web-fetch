# Crawler APIs Integration Summary

## Overview

Successfully integrated multiple web crawling and search APIs into the web-fetch library, providing enhanced web data extraction capabilities while maintaining full backward compatibility.

## Integrated Crawler APIs

### 1. **Firecrawl API** 
- **Features**: Clean markdown conversion, structured data extraction, JavaScript rendering
- **SDK**: `firecrawl-py`
- **Capabilities**: Scrape, Crawl, Search, Extract, Map, JavaScript
- **Best for**: Clean content extraction and markdown conversion

### 2. **Spider.cloud API**
- **Features**: High-performance crawling, JavaScript rendering, proxy support, screenshots
- **SDK**: HTTP API (aiohttp)
- **Capabilities**: Scrape, Crawl, Search, Screenshot, JavaScript, Proxy
- **Best for**: Large-scale crawling and JavaScript-heavy sites

### 3. **Tavily API**
- **Features**: AI-powered search, content extraction, hybrid RAG
- **SDK**: `tavily-python`
- **Capabilities**: Search, Extract, Crawl, Map
- **Best for**: Web search and AI-powered content analysis

### 4. **AnyCrawl API**
- **Features**: Open-source, LLM-friendly output, multi-threaded
- **SDK**: HTTP API (aiohttp)
- **Capabilities**: Scrape, Crawl, Search, Extract
- **Best for**: Self-hosted solutions and custom deployments

## Key Features Implemented

### ✅ Unified Interface
- **CrawlerManager**: Coordinates multiple crawler APIs with automatic fallback
- **Unified Configuration**: Single configuration system for all crawlers
- **Backward Compatibility**: Existing WebFetcher functionality unchanged

### ✅ Fallback Mechanisms
- **Primary/Fallback Order**: Configurable crawler preference and fallback sequence
- **Automatic Retry**: Seamless fallback when primary crawler fails
- **Error Handling**: Comprehensive error handling with detailed error information

### ✅ Configuration Management
- **Environment Variables**: API keys and settings via environment variables
- **Programmatic Config**: Runtime configuration of crawler settings
- **Status Monitoring**: Real-time status of all crawler APIs

### ✅ Enhanced Capabilities
- **Web Search**: AI-powered web search with structured results
- **Website Crawling**: Multi-page crawling with depth and page limits
- **Content Extraction**: CSS selector and schema-based extraction
- **JavaScript Rendering**: Support for dynamic content and SPAs

### ✅ Developer Experience
- **Convenience Functions**: High-level functions for common operations
- **CLI Integration**: Extended CLI with crawler options
- **Comprehensive Testing**: Unit tests and integration tests
- **Rich Documentation**: Detailed guides and examples

## Installation

```bash
# Install with all crawler dependencies
pip install web-fetch[crawlers]

# Or install specific crawler SDKs
pip install firecrawl-py tavily-python
```

## Quick Start

```python
import asyncio
from web_fetch import crawler_fetch_url, CrawlerType

async def main():
    # Basic scraping with automatic crawler selection
    result = await crawler_fetch_url(
        "https://example.com",
        use_crawler=True
    )
    print(result.content)

    # Web search
    from web_fetch import crawler_search_web
    search_result = await crawler_search_web(
        "Python web scraping best practices"
    )
    print(search_result.answer)

asyncio.run(main())
```

## Configuration

### Environment Variables
```bash
export FIRECRAWL_API_KEY="fc-your-api-key"
export SPIDER_API_KEY="your-spider-api-key"
export TAVILY_API_KEY="tvly-your-api-key"
export WEB_FETCH_PRIMARY_CRAWLER="firecrawl"
```

### Programmatic Configuration
```python
from web_fetch import configure_crawler, CrawlerType

configure_crawler(
    CrawlerType.FIRECRAWL,
    api_key="fc-your-key",
    enabled=True
)
```

## CLI Usage

```bash
# Use crawler APIs
web-fetch --use-crawler https://example.com

# Specific crawler
web-fetch --use-crawler --crawler-type firecrawl https://example.com

# Website crawling
web-fetch --use-crawler --crawler-operation crawl --max-pages 10 https://example.com

# Web search
web-fetch --crawler-operation search --search-query "Python tutorials"

# Check crawler status
web-fetch --crawler-status
```

## Architecture

### Core Components

1. **Base Classes** (`crawlers/base.py`)
   - `BaseCrawler`: Abstract base class for all crawlers
   - `CrawlerConfig`: Configuration model
   - `CrawlerRequest`/`CrawlerResult`: Request/response models

2. **Crawler Implementations**
   - `FirecrawlCrawler`: Firecrawl API integration
   - `SpiderCrawler`: Spider.cloud API integration
   - `TavilyCrawler`: Tavily API integration
   - `AnyCrawlCrawler`: AnyCrawl API integration

3. **Management Layer**
   - `CrawlerManager`: Coordinates crawlers with fallback logic
   - `ConfigManager`: Handles configuration and API keys
   - Convenience functions for easy integration

4. **Integration Layer**
   - Extended WebFetcher with crawler support
   - CLI integration with crawler options
   - Backward compatibility with existing code

### Data Flow

```
User Request → CrawlerManager → Primary Crawler → Success/Failure
                    ↓                              ↓
              Fallback Crawler ← ← ← ← ← ← ← ← Failure
                    ↓
              CrawlerResult → FetchResult (backward compatibility)
```

## Testing

```bash
# Run crawler tests
pytest tests/test_crawlers.py

# Run with real APIs (requires API keys)
pytest tests/test_crawlers.py::TestCrawlerIntegration::test_real_api_integration
```

## Documentation

- **[Complete API Documentation](CRAWLER_APIS.md)**: Detailed usage guide
- **[Example Scripts](../examples/crawler_examples.py)**: Comprehensive examples
- **[Configuration Guide](CRAWLER_APIS.md#configuration)**: Setup and configuration
- **[Best Practices](CRAWLER_APIS.md#best-practices)**: Recommended usage patterns

## Performance Considerations

- **Rate Limiting**: Respect API rate limits and implement delays
- **Cost Monitoring**: Monitor API costs for high-volume usage
- **Caching**: Cache results when appropriate to reduce API calls
- **Fallback Strategy**: Configure appropriate fallback order for reliability

## Future Enhancements

- **Additional Crawlers**: Support for more crawler APIs
- **Advanced Caching**: Intelligent caching with TTL and invalidation
- **Batch Operations**: Optimized batch processing for multiple URLs
- **Monitoring Dashboard**: Web-based monitoring and configuration interface

## Migration Guide

### From Standard WebFetcher

```python
# Before
from web_fetch import fetch_url
result = await fetch_url("https://example.com")

# After (with crawler support)
from web_fetch import crawler_fetch_url
result = await crawler_fetch_url("https://example.com", use_crawler=True)

# Or keep existing code unchanged (backward compatible)
result = await fetch_url("https://example.com")  # Still works!
```

### Gradual Adoption

1. **Start with basic usage**: Use `use_crawler=True` parameter
2. **Configure API keys**: Set environment variables for desired crawlers
3. **Customize settings**: Use programmatic configuration for advanced features
4. **Monitor performance**: Use status monitoring to track crawler usage

## Support and Troubleshooting

### Common Issues

1. **API Key Not Found**: Set environment variables correctly
2. **Rate Limiting**: Implement delays and respect API limits
3. **JavaScript Content**: Use crawlers with JavaScript support
4. **Large Sites**: Set appropriate limits for crawling operations

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show detailed crawler operation logs
result = await crawler_fetch_url("https://example.com", use_crawler=True)
```

## Conclusion

The crawler APIs integration provides a powerful, flexible, and backward-compatible enhancement to web-fetch. Users can gradually adopt crawler functionality while maintaining existing code, and benefit from advanced features like AI-powered search, JavaScript rendering, and intelligent fallback mechanisms.

The implementation follows best practices for API integration, error handling, and user experience, making it easy to leverage multiple crawler services through a single, unified interface.
