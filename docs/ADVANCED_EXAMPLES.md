# Advanced Usage Examples

This document provides comprehensive examples for advanced features of the web-fetch library, including FTP operations, crawler integrations, streaming, caching, error handling, and performance optimization.

## Table of Contents

- [Advanced Usage Examples](#advanced-usage-examples)
  - [Table of Contents](#table-of-contents)
  - [FTP Operations](#ftp-operations)
    - [Basic FTP File Operations](#basic-ftp-file-operations)
    - [Parallel FTP Downloads](#parallel-ftp-downloads)
    - [FTP with Resumable Downloads](#ftp-with-resumable-downloads)
  - [Crawler Integration](#crawler-integration)
    - [Multi-Crawler Web Scraping](#multi-crawler-web-scraping)
    - [Content Extraction with Crawlers](#content-extraction-with-crawlers)
  - [Streaming and Large Files](#streaming-and-large-files)
    - [Progressive Download with Progress Tracking](#progressive-download-with-progress-tracking)
    - [Memory-Efficient Stream Processing](#memory-efficient-stream-processing)
  - [Caching Strategies](#caching-strategies)
    - [Multi-Level Caching](#multi-level-caching)
    - [Intelligent Cache Warming](#intelligent-cache-warming)
  - [Error Handling and Resilience](#error-handling-and-resilience)
    - [Circuit Breaker Pattern](#circuit-breaker-pattern)
    - [Comprehensive Error Recovery](#comprehensive-error-recovery)

## FTP Operations

### Basic FTP File Operations

```python
import asyncio
from pathlib import Path
from web_fetch import FTPFetcher, FTPConfig, FTPRequest, FTPAuthType, FTPVerificationMethod

async def basic_ftp_operations():
    """Demonstrate basic FTP file operations."""
    
    # Configure FTP connection
    config = FTPConfig(
        auth_type=FTPAuthType.USER_PASS,
        username="ftpuser",
        password="ftppass",
        connection_timeout=30.0,
        verification_method=FTPVerificationMethod.SHA256
    )
    
    async with FTPFetcher(config) as ftp:
        # List directory contents
        files = await ftp.list_directory("ftp://ftp.example.com/pub/")
        print(f"Found {len(files)} files:")
        for file_info in files:
            print(f"  {file_info.name} ({file_info.size} bytes)")
        
        # Get detailed file information
        file_info = await ftp.get_file_info("ftp://ftp.example.com/pub/data.csv")
        print(f"File: {file_info.name}")
        print(f"Size: {file_info.size} bytes")
        print(f"Modified: {file_info.modified_time}")
        
        # Download a single file
        request = FTPRequest(
            url="ftp://ftp.example.com/pub/data.csv",
            local_path=Path("downloads/data.csv")
        )
        
        result = await ftp.download_file(request)
        if result.is_success:
            print(f"Downloaded {result.bytes_downloaded} bytes in {result.response_time:.2f}s")
        else:
            print(f"Download failed: {result.error}")

asyncio.run(basic_ftp_operations())
```

### Parallel FTP Downloads

```python
import asyncio
from pathlib import Path
from web_fetch import FTPFetcher, FTPConfig, FTPBatchRequest, FTPRequest

async def parallel_ftp_downloads():
    """Demonstrate parallel FTP downloads with progress tracking."""
    
    def progress_callback(progress):
        print(f"Progress: {progress.percentage:.1f}% - {progress.speed_human}")
    
    config = FTPConfig(
        max_concurrent_downloads=5,
        enable_parallel_downloads=True,
        chunk_size=32768,  # 32KB chunks
        verification_method=FTPVerificationMethod.MD5
    )
    
    async with FTPFetcher(config) as ftp:
        # Create batch download request
        requests = [
            FTPRequest(
                url=f"ftp://ftp.example.com/files/file_{i:03d}.dat",
                local_path=Path(f"downloads/file_{i:03d}.dat")
            )
            for i in range(1, 21)  # Download 20 files
        ]
        
        batch_request = FTPBatchRequest(
            requests=requests,
            progress_callback=progress_callback
        )
        
        result = await ftp.download_batch(batch_request)
        
        print(f"Batch download completed:")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Total bytes: {result.total_bytes_downloaded:,}")
        print(f"  Total time: {result.total_time:.2f}s")
        print(f"  Average speed: {result.average_speed_human}")

asyncio.run(parallel_ftp_downloads())
```

### FTP with Resumable Downloads

```python
import asyncio
from pathlib import Path
from web_fetch import FTPFetcher, FTPConfig, FTPRequest

async def resumable_ftp_download():
    """Demonstrate resumable FTP downloads for interrupted transfers."""
    
    config = FTPConfig(
        enable_resume=True,
        verification_method=FTPVerificationMethod.SHA256,
        max_retries=5,
        retry_delay=2.0
    )
    
    async with FTPFetcher(config) as ftp:
        large_file_request = FTPRequest(
            url="ftp://ftp.example.com/large-files/dataset.zip",
            local_path=Path("downloads/dataset.zip")
        )
        
        try:
            result = await ftp.download_file(large_file_request)
            
            if result.is_success:
                print(f"Download completed: {result.bytes_downloaded:,} bytes")
                if result.was_resumed:
                    print(f"Download was resumed from {result.resume_position:,} bytes")
            else:
                print(f"Download failed: {result.error}")
                
        except KeyboardInterrupt:
            print("Download interrupted - can be resumed later")

asyncio.run(resumable_ftp_download())
```

## Crawler Integration

### Multi-Crawler Web Scraping

```python
import asyncio
from web_fetch import (
    crawler_fetch_url, crawler_search_web, crawler_crawl_website,
    configure_crawler, CrawlerType, set_primary_crawler
)

async def multi_crawler_scraping():
    """Demonstrate multi-crawler web scraping with fallback."""
    
    # Configure crawler APIs
    configure_crawler(CrawlerType.FIRECRAWL, api_key="fc-your-key", enabled=True)
    configure_crawler(CrawlerType.SPIDER, api_key="spider-key", enabled=True)
    configure_crawler(CrawlerType.TAVILY, api_key="tvly-key", enabled=True)
    
    # Set primary crawler and fallback order
    set_primary_crawler(CrawlerType.FIRECRAWL)
    
    # Single page scraping with automatic fallback
    result = await crawler_fetch_url(
        "https://example.com/complex-page",
        use_crawler=True,
        enable_javascript=True,
        return_format="markdown"
    )
    
    if result.is_success:
        print(f"Scraped content ({len(result.content)} chars):")
        print(result.content[:500] + "..." if len(result.content) > 500 else result.content)
        print(f"Used crawler: {result.crawler_used}")
    
    # Web search across multiple sources
    search_result = await crawler_search_web(
        "Python web scraping best practices",
        max_results=10,
        include_images=False
    )
    
    if search_result.is_success:
        print(f"\nSearch results ({len(search_result.results)} items):")
        for i, item in enumerate(search_result.results[:3], 1):
            print(f"{i}. {item['title']}")
            print(f"   URL: {item['url']}")
            print(f"   Snippet: {item['snippet'][:100]}...")
    
    # Website crawling with depth control
    crawl_result = await crawler_crawl_website(
        "https://docs.python.org/3/",
        max_pages=50,
        max_depth=3,
        include_domains=["docs.python.org"],
        return_format="text"
    )
    
    if crawl_result.is_success:
        print(f"\nCrawled {len(crawl_result.pages)} pages:")
        for page in crawl_result.pages[:5]:
            print(f"  {page['url']} ({len(page['content'])} chars)")

asyncio.run(multi_crawler_scraping())
```

### Content Extraction with Crawlers

```python
import asyncio
from web_fetch import crawler_extract_content, CrawlerType

async def advanced_content_extraction():
    """Demonstrate advanced content extraction capabilities."""
    
    # Extract structured data from e-commerce page
    ecommerce_result = await crawler_extract_content(
        "https://example-shop.com/product/123",
        extraction_schema={
            "product_name": "h1.product-title",
            "price": ".price-current",
            "description": ".product-description",
            "images": "img.product-image@src",
            "reviews": ".review-item"
        },
        crawler_type=CrawlerType.FIRECRAWL,
        enable_javascript=True
    )
    
    if ecommerce_result.is_success:
        product_data = ecommerce_result.extracted_data
        print(f"Product: {product_data['product_name']}")
        print(f"Price: {product_data['price']}")
        print(f"Images: {len(product_data['images'])} found")
    
    # Extract article content with metadata
    article_result = await crawler_extract_content(
        "https://blog.example.com/article/web-scraping-guide",
        extraction_schema={
            "title": "h1, .article-title",
            "author": ".author-name, .byline",
            "publish_date": ".publish-date, time",
            "content": ".article-content, .post-content",
            "tags": ".tag, .category"
        },
        return_format="markdown",
        include_metadata=True
    )
    
    if article_result.is_success:
        article = article_result.extracted_data
        metadata = article_result.metadata
        
        print(f"\nArticle: {article['title']}")
        print(f"Author: {article['author']}")
        print(f"Published: {article['publish_date']}")
        print(f"Word count: {metadata.get('word_count', 'N/A')}")
        print(f"Reading time: {metadata.get('reading_time', 'N/A')} minutes")

asyncio.run(advanced_content_extraction())
```

## Streaming and Large Files

### Progressive Download with Progress Tracking

```python
import asyncio
from pathlib import Path
from web_fetch import StreamingWebFetcher, StreamRequest, ProgressInfo

async def progressive_download():
    """Demonstrate progressive download with detailed progress tracking."""
    
    class ProgressTracker:
        def __init__(self):
            self.start_time = None
            self.last_update = None
            
        def __call__(self, progress: ProgressInfo):
            import time
            
            if self.start_time is None:
                self.start_time = time.time()
                self.last_update = self.start_time
            
            current_time = time.time()
            
            # Update every 2 seconds
            if current_time - self.last_update >= 2.0:
                elapsed = current_time - self.start_time
                
                if progress.total_bytes:
                    percentage = progress.percentage or 0
                    eta_seconds = (elapsed / (percentage / 100)) - elapsed if percentage > 0 else 0
                    eta_str = f"{eta_seconds:.0f}s" if eta_seconds > 0 else "Unknown"
                    
                    print(f"Progress: {percentage:.1f}% "
                          f"({progress.bytes_downloaded:,}/{progress.total_bytes:,} bytes) "
                          f"Speed: {progress.speed_human} "
                          f"ETA: {eta_str}")
                else:
                    print(f"Downloaded: {progress.bytes_downloaded:,} bytes "
                          f"Speed: {progress.speed_human}")
                
                self.last_update = current_time
    
    progress_tracker = ProgressTracker()
    
    async with StreamingWebFetcher() as fetcher:
        # Download large dataset with progress tracking
        request = StreamRequest(
            url="https://example.com/datasets/large-dataset.csv",
            output_path=Path("downloads/large-dataset.csv"),
            chunk_size=64 * 1024,  # 64KB chunks
            max_file_size=500 * 1024 * 1024,  # 500MB limit
            enable_resume=True
        )
        
        result = await fetcher.stream_fetch(request, progress_tracker)
        
        if result.is_success:
            print(f"\nDownload completed!")
            print(f"Total bytes: {result.bytes_downloaded:,}")
            print(f"Total time: {result.total_time:.2f}s")
            print(f"Average speed: {result.average_speed_human}")
            print(f"Peak speed: {result.peak_speed_human}")
        else:
            print(f"Download failed: {result.error}")

asyncio.run(progressive_download())
```

### Memory-Efficient Stream Processing

```python
import asyncio
import csv
from io import StringIO
from web_fetch import StreamingWebFetcher, StreamRequest

async def stream_processing():
    """Demonstrate memory-efficient processing of streamed data."""
    
    class CSVProcessor:
        def __init__(self):
            self.row_count = 0
            self.buffer = ""
            self.processed_rows = []
        
        def process_chunk(self, chunk_data: bytes):
            # Convert bytes to string and add to buffer
            text_chunk = chunk_data.decode('utf-8', errors='ignore')
            self.buffer += text_chunk
            
            # Process complete lines
            lines = self.buffer.split('\n')
            self.buffer = lines[-1]  # Keep incomplete line in buffer
            
            for line in lines[:-1]:
                if line.strip():
                    try:
                        # Process CSV row
                        reader = csv.reader([line])
                        row = next(reader)
                        self.processed_rows.append(row)
                        self.row_count += 1
                        
                        # Process in batches to manage memory
                        if len(self.processed_rows) >= 1000:
                            self.process_batch(self.processed_rows)
                            self.processed_rows = []
                            
                    except csv.Error:
                        continue  # Skip malformed rows
        
        def process_batch(self, rows):
            # Process batch of rows (e.g., save to database, analyze, etc.)
            print(f"Processed batch of {len(rows)} rows (total: {self.row_count})")
        
        def finalize(self):
            # Process remaining rows
            if self.processed_rows:
                self.process_batch(self.processed_rows)
            
            # Process any remaining buffer content
            if self.buffer.strip():
                try:
                    reader = csv.reader([self.buffer])
                    row = next(reader)
                    self.row_count += 1
                    print(f"Processed final row (total: {self.row_count})")
                except csv.Error:
                    pass
    
    processor = CSVProcessor()
    
    # Custom progress callback that also processes data
    def progress_and_process(progress: ProgressInfo):
        if hasattr(progress, 'chunk_data'):
            processor.process_chunk(progress.chunk_data)
        
        if progress.percentage:
            print(f"Progress: {progress.percentage:.1f}% - "
                  f"Processed {processor.row_count} rows")
    
    async with StreamingWebFetcher() as fetcher:
        request = StreamRequest(
            url="https://example.com/data/large-dataset.csv",
            chunk_size=32 * 1024,  # 32KB chunks
            process_chunks=True  # Enable chunk processing
        )
        
        result = await fetcher.stream_fetch(request, progress_and_process)
        
        # Finalize processing
        processor.finalize()
        
        print(f"Stream processing completed:")
        print(f"Total rows processed: {processor.row_count}")
        print(f"Total bytes streamed: {result.bytes_downloaded:,}")

asyncio.run(stream_processing())
```

## Caching Strategies

### Multi-Level Caching

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType
from web_fetch.utils import EnhancedCacheConfig, SimpleCache

async def multi_level_caching():
    """Demonstrate multi-level caching strategies."""

    # Configure enhanced caching with Redis backend
    cache_config = EnhancedCacheConfig(
        backend="redis",
        ttl_seconds=3600,  # 1 hour
        max_size=10000,
        enable_compression=True,
        redis_config={
            "host": "localhost",
            "port": 6379,
            "db": 1
        }
    )

    # Create fetcher with caching enabled
    config = FetchConfig(max_concurrent_requests=20)

    async with WebFetcher(
        config=config,
        cache_config=cache_config,
        enable_metrics=True
    ) as fetcher:

        # First request - will be cached
        request = FetchRequest(
            url="https://api.example.com/expensive-operation",
            content_type=ContentType.JSON
        )

        print("First request (cache miss):")
        result1 = await fetcher.fetch_single(request)
        print(f"Response time: {result1.response_time:.2f}s")

        # Second request - should hit cache
        print("\nSecond request (cache hit):")
        result2 = await fetcher.fetch_single(request)
        print(f"Response time: {result2.response_time:.2f}s")

        # Verify cache hit
        if result2.response_time < result1.response_time * 0.1:
            print("✓ Cache hit detected!")

        # Cache with custom TTL
        custom_request = FetchRequest(
            url="https://api.example.com/frequently-changing-data",
            content_type=ContentType.JSON,
            headers={"Cache-TTL": "300"}  # 5 minutes
        )

        result3 = await fetcher.fetch_single(custom_request)
        print(f"\nCustom TTL request: {result3.response_time:.2f}s")

asyncio.run(multi_level_caching())
```

### Intelligent Cache Warming

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, BatchFetchRequest

async def intelligent_cache_warming():
    """Demonstrate intelligent cache warming strategies."""

    async def warm_cache_for_user_session(user_id: str):
        """Warm cache with data likely to be needed by user."""

        # Predict URLs user might access based on patterns
        predicted_urls = [
            f"https://api.example.com/user/{user_id}/profile",
            f"https://api.example.com/user/{user_id}/preferences",
            f"https://api.example.com/user/{user_id}/recent-activity",
            "https://api.example.com/global/notifications",
            "https://api.example.com/global/announcements"
        ]

        # Create batch request for cache warming
        warm_requests = [
            FetchRequest(url=url, content_type=ContentType.JSON)
            for url in predicted_urls
        ]

        batch_request = BatchFetchRequest(
            requests=warm_requests,
            fail_fast=False  # Continue even if some requests fail
        )

        async with WebFetcher(enable_metrics=True) as fetcher:
            result = await fetcher.fetch_batch(batch_request)

            print(f"Cache warming completed for user {user_id}:")
            print(f"  Success rate: {result.success_rate:.1f}%")
            print(f"  Total time: {result.total_time:.2f}s")
            print(f"  Cached {len(result.successful_results)} resources")

    # Warm cache for multiple users
    user_ids = ["user123", "user456", "user789"]

    tasks = [warm_cache_for_user_session(uid) for uid in user_ids]
    await asyncio.gather(*tasks)

    print("\nCache warming completed for all users")

asyncio.run(intelligent_cache_warming())
```

## Error Handling and Resilience

### Circuit Breaker Pattern

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest
from web_fetch.utils import CircuitBreakerConfig, with_circuit_breaker

async def circuit_breaker_example():
    """Demonstrate circuit breaker pattern for resilient requests."""

    # Configure circuit breaker
    cb_config = CircuitBreakerConfig(
        failure_threshold=3,      # Open after 3 failures
        recovery_timeout=10.0,    # Try to recover after 10s
        success_threshold=2,      # Close after 2 successes
        failure_exceptions=(ConnectionError, TimeoutError),
        failure_status_codes={500, 502, 503, 504}
    )

    config = FetchConfig(
        max_retries=1,  # Minimal retries, let circuit breaker handle it
        total_timeout=5.0
    )

    async with WebFetcher(
        config=config,
        circuit_breaker_config=cb_config,
        enable_metrics=True
    ) as fetcher:

        # Simulate requests to a failing service
        failing_url = "https://httpbin.org/status/500"  # Always returns 500

        for i in range(10):
            try:
                request = FetchRequest(url=failing_url)
                result = await fetcher.fetch_with_circuit_breaker(request)

                if result.is_success:
                    print(f"Request {i+1}: SUCCESS")
                else:
                    print(f"Request {i+1}: FAILED - {result.error}")

            except Exception as e:
                print(f"Request {i+1}: BLOCKED - {e}")

            await asyncio.sleep(1)  # Wait between requests

        # Get circuit breaker statistics
        stats = fetcher.get_circuit_breaker_stats()
        print(f"\nCircuit Breaker Stats:")
        print(f"  Total requests: {stats.total_requests}")
        print(f"  Failed requests: {stats.failed_requests}")
        print(f"  Blocked requests: {stats.blocked_requests}")
        print(f"  State changes: {stats.state_changes}")

asyncio.run(circuit_breaker_example())
```

### Comprehensive Error Recovery

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, BatchFetchRequest
from web_fetch.exceptions import WebFetchError, TimeoutError, ConnectionError

async def comprehensive_error_recovery():
    """Demonstrate comprehensive error recovery strategies."""

    class ResilientFetcher:
        def __init__(self):
            self.config = FetchConfig(
                max_retries=3,
                retry_delay=1.0,
                total_timeout=30.0
            )
            self.fallback_urls = {}
            self.error_counts = {}

        def add_fallback(self, primary_url: str, fallback_url: str):
            """Add fallback URL for a primary URL."""
            self.fallback_urls[primary_url] = fallback_url

        async def resilient_fetch(self, url: str, **kwargs) -> dict:
            """Fetch with comprehensive error recovery."""

            async with WebFetcher(self.config) as fetcher:
                # Try primary URL
                try:
                    request = FetchRequest(url=url, **kwargs)
                    result = await fetcher.fetch_single(request)

                    if result.is_success:
                        # Reset error count on success
                        self.error_counts[url] = 0
                        return {
                            "success": True,
                            "data": result.content,
                            "source": "primary",
                            "url": url
                        }
                    else:
                        raise WebFetchError(result.error)

                except Exception as e:
                    print(f"Primary URL failed: {e}")
                    self.error_counts[url] = self.error_counts.get(url, 0) + 1

                    # Try fallback URL if available
                    if url in self.fallback_urls:
                        fallback_url = self.fallback_urls[url]
                        try:
                            fallback_request = FetchRequest(url=fallback_url, **kwargs)
                            fallback_result = await fetcher.fetch_single(fallback_request)

                            if fallback_result.is_success:
                                return {
                                    "success": True,
                                    "data": fallback_result.content,
                                    "source": "fallback",
                                    "url": fallback_url
                                }
                        except Exception as fallback_error:
                            print(f"Fallback URL also failed: {fallback_error}")

                    # Return error information
                    return {
                        "success": False,
                        "error": str(e),
                        "error_count": self.error_counts[url],
                        "url": url
                    }

    # Usage example
    fetcher = ResilientFetcher()

    # Configure fallback URLs
    fetcher.add_fallback(
        "https://api.primary.com/data",
        "https://api.backup.com/data"
    )
    fetcher.add_fallback(
        "https://service.main.com/status",
        "https://status.backup.com/health"
    )

    # Test resilient fetching
    urls_to_test = [
        "https://httpbin.org/json",  # Should work
        "https://httpbin.org/status/500",  # Will fail
        "https://api.primary.com/data",  # Will use fallback
    ]

    for url in urls_to_test:
        result = await fetcher.resilient_fetch(url, content_type="json")

        if result["success"]:
            print(f"✓ {url} -> {result['source']} source")
        else:
            print(f"✗ {url} -> Failed after {result['error_count']} attempts")

asyncio.run(comprehensive_error_recovery())
```
