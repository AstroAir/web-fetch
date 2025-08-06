# Crawler APIs Integration

This document provides comprehensive documentation for the integrated crawler APIs in web-fetch, including setup guides, configuration examples, and usage patterns.

## Overview

Web-fetch now supports multiple crawler APIs that provide enhanced web scraping and crawling capabilities:

- **Firecrawl**: Clean markdown conversion and structured data extraction
- **Spider.cloud**: High-performance crawling with JavaScript rendering
- **Tavily**: AI-powered search and content extraction
- **AnyCrawl**: Open-source, LLM-friendly crawler

## Quick Start

### Installation

Install web-fetch with crawler support:

```bash
# Install with all crawler dependencies
pip install web-fetch[crawlers]

# Or install specific crawler SDKs
pip install firecrawl-py tavily-python
```

### Basic Usage

```python
import asyncio
from web_fetch import crawler_fetch_url, CrawlerType

async def main():
    # Use crawler APIs for enhanced scraping
    result = await crawler_fetch_url(
        "https://example.com",
        use_crawler=True,
        crawler_type=CrawlerType.FIRECRAWL
    )
    print(result.content)

asyncio.run(main())
```

## Configuration

### Environment Variables

Set API keys using environment variables:

```bash
export FIRECRAWL_API_KEY="fc-your-api-key"
export SPIDER_API_KEY="your-spider-api-key"
export TAVILY_API_KEY="tvly-your-api-key"
export ANYCRAWL_API_KEY="your-anycrawl-key"  # Optional for self-hosted

# Configure primary crawler
export WEB_FETCH_PRIMARY_CRAWLER="firecrawl"
export WEB_FETCH_ENABLE_FALLBACK="true"
```

### Programmatic Configuration

```python
from web_fetch import configure_crawler, set_primary_crawler, CrawlerType

# Configure individual crawlers
configure_crawler(
    CrawlerType.FIRECRAWL,
    api_key="fc-your-api-key",
    enabled=True
)

configure_crawler(
    CrawlerType.SPIDER,
    api_key="your-spider-key",
    enabled=True,
    use_proxy=True,
    proxy_country="US"
)

# Set primary crawler and fallback order
set_primary_crawler(CrawlerType.FIRECRAWL)
set_fallback_order([CrawlerType.SPIDER, CrawlerType.TAVILY])
```

## Usage Examples

### Basic Web Scraping

```python
import asyncio
from web_fetch import crawler_fetch_url

async def scrape_page():
    # Scrape a single page with automatic crawler selection
    result = await crawler_fetch_url(
        "https://example.com/article",
        use_crawler=True,
        return_format="markdown",
        include_metadata=True
    )
    
    print(f"Title: {result.title}")
    print(f"Content: {result.content}")
    return result

asyncio.run(scrape_page())
```

### Website Crawling

```python
import asyncio
from web_fetch import crawler_crawl_website

async def crawl_site():
    # Crawl an entire website
    result = await crawler_crawl_website(
        "https://docs.example.com",
        max_pages=50,
        max_depth=3,
        include_links=True
    )
    
    print(f"Crawled {result.pages_crawled} pages")
    print(f"Found {len(result.links)} links")
    return result

asyncio.run(crawl_site())
```

### Web Search

```python
import asyncio
from web_fetch import crawler_search_web

async def search_web():
    # Search the web using AI-powered crawlers
    result = await crawler_search_web(
        "Python web scraping best practices",
        max_results=10
    )
    
    print(f"AI Answer: {result.answer}")
    for search_result in result.search_results:
        print(f"- {search_result['title']}: {search_result['url']}")
    
    return result

asyncio.run(search_web())
```

### Content Extraction

```python
import asyncio
from web_fetch import crawler_extract_content

async def extract_content():
    # Extract specific content using CSS selectors
    result = await crawler_extract_content(
        "https://news.example.com/article",
        css_selector="article .content",
        include_images=True
    )
    
    print(f"Extracted content: {result.content}")
    print(f"Images found: {len(result.images)}")
    return result

asyncio.run(extract_content())
```

### Batch Processing

```python
import asyncio
from web_fetch import crawler_fetch_urls

async def batch_scrape():
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3"
    ]
    
    # Process multiple URLs concurrently
    results = await crawler_fetch_urls(
        urls,
        use_crawler=True,
        max_pages=1,  # Scrape only, don't crawl
        return_format="markdown"
    )
    
    for result in results:
        print(f"URL: {result.url}")
        print(f"Success: {result.is_success}")
        print(f"Content length: {len(result.content) if result.content else 0}")
    
    return results

asyncio.run(batch_scrape())
```

## Advanced Configuration

### Custom Crawler Settings

```python
from web_fetch import CrawlerManager, CrawlerConfig, CrawlerType

# Create custom configurations
firecrawl_config = CrawlerConfig(
    api_key="fc-your-key",
    timeout=60.0,
    return_format="markdown",
    include_metadata=True,
    include_links=True,
    enable_javascript=True
)

spider_config = CrawlerConfig(
    api_key="spider-key",
    timeout=120.0,
    use_proxy=True,
    proxy_country="US",
    enable_javascript=True,
    wait_for_selector=".content"
)

# Create manager with custom configs
manager = CrawlerManager(
    primary_crawler=CrawlerType.FIRECRAWL,
    fallback_crawlers=[CrawlerType.SPIDER, CrawlerType.TAVILY],
    crawler_configs={
        CrawlerType.FIRECRAWL: firecrawl_config,
        CrawlerType.SPIDER: spider_config
    }
)
```

### Error Handling and Fallbacks

```python
import asyncio
from web_fetch import crawler_fetch_url, CrawlerError, CrawlerType

async def robust_scraping():
    try:
        # Try with primary crawler
        result = await crawler_fetch_url(
            "https://difficult-site.com",
            use_crawler=True,
            crawler_type=CrawlerType.FIRECRAWL
        )
        return result
    
    except CrawlerError as e:
        print(f"Crawler failed: {e}")
        
        # Fallback to different crawler
        try:
            result = await crawler_fetch_url(
                "https://difficult-site.com",
                use_crawler=True,
                crawler_type=CrawlerType.SPIDER,
                enable_javascript=True,
                use_proxy=True
            )
            return result
        except CrawlerError:
            # Final fallback to standard HTTP
            result = await crawler_fetch_url(
                "https://difficult-site.com",
                use_crawler=False  # Use standard WebFetcher
            )
            return result

asyncio.run(robust_scraping())
```

## Crawler-Specific Features

### Firecrawl Features

```python
# Clean markdown conversion
result = await crawler_fetch_url(
    "https://blog.example.com/post",
    use_crawler=True,
    crawler_type=CrawlerType.FIRECRAWL,
    return_format="markdown",
    include_metadata=True
)

# Structured data extraction
result = await crawler_extract_content(
    "https://ecommerce.example.com/product",
    crawler_type=CrawlerType.FIRECRAWL,
    extract_schema={
        "name": "string",
        "price": "number",
        "description": "string"
    }
)
```

### Spider.cloud Features

```python
# High-performance crawling with JavaScript
result = await crawler_crawl_website(
    "https://spa-app.example.com",
    crawler_type=CrawlerType.SPIDER,
    max_pages=100,
    enable_javascript=True,
    use_proxy=True,
    proxy_country="US",
    wait_for_selector=".dynamic-content"
)

# Screenshot capability
result = await crawler_fetch_url(
    "https://example.com",
    crawler_type=CrawlerType.SPIDER,
    operation=CrawlerCapability.SCREENSHOT
)
```

### Tavily Features

```python
# AI-powered search with answers
result = await crawler_search_web(
    "What are the latest developments in AI?",
    crawler_type=CrawlerType.TAVILY,
    max_results=10,
    search_depth="advanced",
    include_images=True
)

print(f"AI Answer: {result.answer}")
print(f"Search Results: {len(result.search_results)}")
```

## Monitoring and Status

### Check Crawler Status

```python
from web_fetch import get_crawler_status

# Get status of all crawlers
status = get_crawler_status()
print(f"Primary crawler: {status['primary_crawler']}")
print(f"Enabled crawlers: {status['enabled_crawlers']}")

for crawler, info in status['crawler_status'].items():
    print(f"{crawler}: enabled={info['enabled']}, has_key={info['has_api_key']}")
```

### Performance Monitoring

```python
import time
from web_fetch import crawler_fetch_url

async def monitor_performance():
    start_time = time.time()
    
    result = await crawler_fetch_url(
        "https://example.com",
        use_crawler=True
    )
    
    end_time = time.time()
    
    print(f"Response time: {result.response_time:.2f}s")
    print(f"Total time: {end_time - start_time:.2f}s")
    print(f"Pages crawled: {result.pages_crawled}")
    print(f"Cost: ${result.total_cost:.4f}" if result.total_cost else "Cost: N/A")
    
    return result
```

## Best Practices

1. **API Key Management**: Store API keys in environment variables, not in code
2. **Rate Limiting**: Respect API rate limits and use appropriate delays
3. **Error Handling**: Always implement fallback mechanisms
4. **Cost Monitoring**: Monitor API costs, especially for high-volume usage
5. **Content Caching**: Cache results when appropriate to reduce API calls
6. **Selective Crawling**: Use domain filtering and depth limits to control scope

## Troubleshooting

### Common Issues

1. **API Key Not Found**: Ensure environment variables are set correctly
2. **Rate Limiting**: Implement delays and respect API limits
3. **JavaScript Content**: Use crawlers with JavaScript support for SPAs
4. **Large Sites**: Set appropriate limits for crawling operations
5. **Network Issues**: Implement retry logic and fallback mechanisms

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('web_fetch.crawlers')

# This will show detailed crawler operation logs
result = await crawler_fetch_url("https://example.com", use_crawler=True)
```
