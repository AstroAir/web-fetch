#!/usr/bin/env python3
"""
Comprehensive examples for using crawler APIs with web-fetch.

This script demonstrates various crawler API features including:
- Basic scraping with different crawlers
- Website crawling
- Web search functionality
- Content extraction
- Configuration and error handling
"""

import asyncio
import os
import logging
from typing import Any, Dict, List, Optional

from web_fetch import (
    crawler_fetch_url,
    crawler_fetch_urls,
    crawler_search_web,
    crawler_crawl_website,
    crawler_extract_content,
    configure_crawler,
    set_primary_crawler,
    get_crawler_status,
    CrawlerType,
    CrawlerCapability,
    CrawlerManager,
)

# Import these separately to help IDE recognition
from web_fetch import CrawlerConfig, CrawlerRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_scraping() -> Optional[Any]:
    """Example 1: Basic web scraping with crawler APIs."""
    print("\n=== Example 1: Basic Web Scraping ===")
    
    try:
        # Scrape a single page using automatic crawler selection
        result = await crawler_fetch_url(
            "https://httpbin.org/html",
            use_crawler=True,
            return_format="markdown",
            include_metadata=True
        )
        
        print(f"✓ Successfully scraped page")
        print(f"  Status: {result.status_code}")
        print(f"  Content length: {len(result.content) if result.content else 0}")
        print(f"  Response time: {result.response_time:.2f}s")
        
        return result
        
    except Exception as e:
        print(f"✗ Scraping failed: {e}")
        return None


async def example_specific_crawler() -> Optional[Any]:
    """Example 2: Using a specific crawler (Firecrawl)."""
    print("\n=== Example 2: Specific Crawler (Firecrawl) ===")
    
    # Configure Firecrawl if API key is available
    firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
    if not firecrawl_key:
        print("⚠ FIRECRAWL_API_KEY not set, skipping example")
        return None
    
    try:
        configure_crawler(
            CrawlerType.FIRECRAWL,
            api_key=firecrawl_key,
            enabled=True
        )
        
        result = await crawler_fetch_url(
            "https://httpbin.org/html",
            use_crawler=True,
            crawler_type=CrawlerType.FIRECRAWL,
            return_format="markdown",
            include_metadata=True,
            include_links=True
        )
        
        print(f"✓ Firecrawl scraping successful")
        print(f"  Status: {result.status_code}")
        if result.content and isinstance(result.content, str):
            print(f"  Content preview: {result.content[:100]}...")

        return result
        
    except Exception as e:
        print(f"✗ Firecrawl scraping failed: {e}")
        return None


async def example_web_search() -> Optional[Any]:
    """Example 3: Web search using Tavily."""
    print("\n=== Example 3: Web Search (Tavily) ===")
    
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("⚠ TAVILY_API_KEY not set, skipping example")
        return None
    
    try:
        configure_crawler(
            CrawlerType.TAVILY,
            api_key=tavily_key,
            enabled=True
        )
        
        result = await crawler_search_web(
            "Python web scraping best practices 2024",
            max_results=5,
            crawler_type=CrawlerType.TAVILY
        )
        
        print(f"✓ Web search successful")
        print(f"  Status: {result.status_code}")

        # Search results are stored in the content field as a dict
        if result.content and isinstance(result.content, dict):
            search_results = result.content.get('results', [])
            print(f"  Results found: {len(search_results)}")

            if 'answer' in result.content:
                answer = result.content['answer']
                print(f"  AI Answer: {answer[:200]}...")

            print("  Top results:")
            for i, search_result in enumerate(search_results[:3], 1):
                title = search_result.get('title', 'No title')
                url = search_result.get('url', 'No URL')
                print(f"    {i}. {title}")
                print(f"       {url}")

        return result
        
    except Exception as e:
        print(f"✗ Web search failed: {e}")
        return None


async def example_website_crawling() -> Optional[Any]:
    """Example 4: Website crawling with Spider.cloud."""
    print("\n=== Example 4: Website Crawling (Spider.cloud) ===")
    
    spider_key = os.getenv('SPIDER_API_KEY')
    if not spider_key:
        print("⚠ SPIDER_API_KEY not set, skipping example")
        return None
    
    try:
        configure_crawler(
            CrawlerType.SPIDER,
            api_key=spider_key,
            enabled=True
        )
        
        result = await crawler_crawl_website(
            "https://httpbin.org",
            max_pages=5,
            max_depth=2,
            crawler_type=CrawlerType.SPIDER,
            include_links=True
        )
        
        print(f"✓ Website crawling successful")
        print(f"  Status: {result.status_code}")
        print(f"  Links found: {len(result.links)}")

        # Crawl metadata might be in content or structured_data
        if result.structured_data:
            pages_crawled = result.structured_data.get('pages_crawled', 'Unknown')
            total_cost = result.structured_data.get('total_cost')
            print(f"  Pages crawled: {pages_crawled}")
            if total_cost:
                print(f"  Total cost: ${total_cost:.4f}")

        return result
        
    except Exception as e:
        print(f"✗ Website crawling failed: {e}")
        return None


async def example_content_extraction() -> Optional[Any]:
    """Example 5: Content extraction with CSS selectors."""
    print("\n=== Example 5: Content Extraction ===")
    
    try:
        result = await crawler_extract_content(
            "https://httpbin.org/html",
            css_selector="body",
            use_crawler=True,
            include_metadata=True
        )
        
        print(f"✓ Content extraction successful")
        print(f"  Extracted content length: {len(result.content) if result.content else 0}")
        
        return result
        
    except Exception as e:
        print(f"✗ Content extraction failed: {e}")
        return None


async def example_batch_processing() -> Optional[List[Any]]:
    """Example 6: Batch processing multiple URLs."""
    print("\n=== Example 6: Batch Processing ===")
    
    urls = [
        "https://httpbin.org/html",
        "https://httpbin.org/json",
        "https://httpbin.org/xml",
    ]
    
    try:
        results = await crawler_fetch_urls(
            urls,  # type: ignore[arg-type]
            use_crawler=True,
            return_format="markdown",
            include_metadata=True
        )
        
        print(f"✓ Batch processing successful")
        print(f"  URLs processed: {len(results)}")
        
        for i, result in enumerate(results, 1):
            status = "✓" if result.is_success else "✗"
            print(f"  {i}. {status} {result.url} ({result.status_code})")
        
        return results
        
    except Exception as e:
        print(f"✗ Batch processing failed: {e}")
        return None


async def example_fallback_mechanism() -> Optional[Any]:
    """Example 7: Demonstrating fallback mechanisms."""
    print("\n=== Example 7: Fallback Mechanisms ===")
    
    try:
        # Configure multiple crawlers
        available_crawlers: List[CrawlerType] = []
        
        if os.getenv('FIRECRAWL_API_KEY'):
            configure_crawler(CrawlerType.FIRECRAWL, api_key=os.getenv('FIRECRAWL_API_KEY'))
            available_crawlers.append(CrawlerType.FIRECRAWL)
        
        if os.getenv('SPIDER_API_KEY'):
            configure_crawler(CrawlerType.SPIDER, api_key=os.getenv('SPIDER_API_KEY'))
            available_crawlers.append(CrawlerType.SPIDER)
        
        if os.getenv('TAVILY_API_KEY'):
            configure_crawler(CrawlerType.TAVILY, api_key=os.getenv('TAVILY_API_KEY'))
            available_crawlers.append(CrawlerType.TAVILY)
        
        if not available_crawlers:
            print("⚠ No crawler API keys configured, skipping fallback example")
            return None
        
        # Set primary and fallback order
        set_primary_crawler(available_crawlers[0])
        
        # Try scraping with automatic fallback
        result = await crawler_fetch_url(
            "https://httpbin.org/html",
            use_crawler=True,
            return_format="markdown"
        )
        
        print(f"✓ Fallback mechanism successful")
        print(f"  Status: {result.status_code}")
        print(f"  Content length: {len(str(result.content)) if result.content else 0}")

        return result
        
    except Exception as e:
        print(f"✗ Fallback mechanism failed: {e}")
        return None


async def example_custom_manager() -> Optional[Any]:
    """Example 8: Using custom CrawlerManager configuration."""
    print("\n=== Example 8: Custom CrawlerManager ===")
    
    try:
        # Create custom configurations
        configs: Dict[CrawlerType, CrawlerConfig] = {}
        
        if os.getenv('FIRECRAWL_API_KEY'):
            configs[CrawlerType.FIRECRAWL] = CrawlerConfig(
                api_key=os.getenv('FIRECRAWL_API_KEY'),
                timeout=60.0,
                return_format="markdown",
                include_metadata=True,
                include_links=True
            )
        
        if os.getenv('SPIDER_API_KEY'):
            configs[CrawlerType.SPIDER] = CrawlerConfig(
                api_key=os.getenv('SPIDER_API_KEY'),
                timeout=120.0,
                enable_javascript=True,
                use_proxy=False
            )
        
        if not configs:
            print("⚠ No crawler API keys configured, skipping custom manager example")
            return None
        
        # Create custom manager
        manager = CrawlerManager(
            primary_crawler=list(configs.keys())[0],
            fallback_crawlers=list(configs.keys())[1:],
            crawler_configs=configs
        )
        
        # Create custom request
        from pydantic import TypeAdapter, HttpUrl
        adapter = TypeAdapter(HttpUrl)
        request = CrawlerRequest(
            url=adapter.validate_python("https://httpbin.org/html"),
            operation=CrawlerCapability.SCRAPE
        )
        
        # Execute request
        crawler_result = await manager.execute_request(request)

        print(f"✓ Custom manager successful")
        print(f"  Crawler used: {crawler_result.crawler_type}")
        print(f"  Operation: {crawler_result.operation}")
        print(f"  Success: {crawler_result.is_success}")

        # Convert to FetchResult for consistency with other examples
        result = crawler_result.to_fetch_result()
        return result
        
    except Exception as e:
        print(f"✗ Custom manager failed: {e}")
        return None


def example_status_monitoring() -> Optional[Dict[str, Any]]:
    """Example 9: Monitoring crawler status."""
    print("\n=== Example 9: Status Monitoring ===")
    
    try:
        status = get_crawler_status()
        
        print(f"✓ Status retrieved successfully")
        print(f"  Primary crawler: {status['primary_crawler']}")
        print(f"  Enabled crawlers: {', '.join(status['enabled_crawlers'])}")
        print(f"  Fallback enabled: {status.get('enable_fallback', 'N/A')}")
        
        print("\n  Crawler details:")
        for crawler, info in status['crawler_status'].items():
            enabled = "✓" if info['enabled'] else "✗"
            has_key = "✓" if info['has_api_key'] else "✗"
            print(f"    {crawler}: enabled={enabled}, api_key={has_key}")
        
        return status
        
    except Exception as e:
        print(f"✗ Status monitoring failed: {e}")
        return None


async def run_all_examples() -> None:
    """Run all examples in sequence."""
    print("🚀 Running Web-Fetch Crawler API Examples")
    print("=" * 50)
    
    # Check for API keys
    api_keys = {
        'FIRECRAWL_API_KEY': os.getenv('FIRECRAWL_API_KEY'),
        'SPIDER_API_KEY': os.getenv('SPIDER_API_KEY'),
        'TAVILY_API_KEY': os.getenv('TAVILY_API_KEY'),
        'ANYCRAWL_API_KEY': os.getenv('ANYCRAWL_API_KEY'),
    }
    
    print("\n📋 API Key Status:")
    for key, value in api_keys.items():
        status = "✓ Set" if value else "✗ Not set"
        print(f"  {key}: {status}")
    
    if not any(api_keys.values()):
        print("\n⚠ Warning: No API keys configured. Some examples will be skipped.")
        print("   Set environment variables to test specific crawlers:")
        for key in api_keys.keys():
            print(f"   export {key}='your-api-key'")
    
    # Run examples
    examples = [
        ("Basic Scraping", example_basic_scraping),
        ("Specific Crawler", example_specific_crawler),
        ("Web Search", example_web_search),
        ("Website Crawling", example_website_crawling),
        ("Content Extraction", example_content_extraction),
        ("Batch Processing", example_batch_processing),
        ("Fallback Mechanisms", example_fallback_mechanism),
        ("Custom Manager", example_custom_manager),
        ("Status Monitoring", example_status_monitoring),
    ]
    
    results: Dict[str, Optional[Any]] = {}
    
    for name, example_func in examples:
        try:
            if asyncio.iscoroutinefunction(example_func):
                result = await example_func()
            else:
                result = example_func()
            results[name] = result
        except Exception as e:
            print(f"✗ Example '{name}' failed with error: {e}")
            results[name] = None
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Examples Summary:")
    
    successful = sum(1 for result in results.values() if result is not None)
    total = len(results)
    
    print(f"  Successful: {successful}/{total}")
    
    for name, result in results.items():
        status = "✓" if result is not None else "✗"
        print(f"  {status} {name}")
    
    print(f"\n🎉 Examples completed! {successful}/{total} successful.")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(run_all_examples())
