#!/usr/bin/env python3
"""
Comprehensive CLI examples for the web-fetch library.

This script demonstrates all CLI features and provides copy-paste examples
for various command-line scenarios including basic fetching, batch processing,
streaming, caching, crawler operations, and advanced configurations.
"""

import subprocess
import sys
from pathlib import Path
from typing import List


def run_command(cmd: List[str], description: str) -> None:
    """Run a CLI command and display the result."""
    print(f"\n{'='*60}")
    print(f"Example: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.stdout:
            print("Output:")
            print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        print(f"Exit code: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("Command timed out after 30 seconds")
    except Exception as e:
        print(f"Error running command: {e}")


def basic_http_examples() -> None:
    """Demonstrate basic HTTP fetching via CLI."""
    print("\n" + "="*80)
    print("BASIC HTTP FETCHING EXAMPLES")
    print("="*80)
    
    examples = [
        # Simple GET requests
        (["web-fetch", "https://httpbin.org/get"], 
         "Simple GET request (default text output)"),
        
        (["web-fetch", "-t", "json", "https://httpbin.org/json"], 
         "Fetch and parse as JSON"),
        
        (["web-fetch", "-t", "html", "https://httpbin.org/html"], 
         "Fetch and parse HTML with structured data extraction"),
        
        (["web-fetch", "--timeout", "10", "https://httpbin.org/delay/2"], 
         "Custom timeout (10 seconds)"),
        
        # Custom headers
        (["web-fetch", "--headers", "User-Agent: MyApp/1.0", 
          "--headers", "Accept: application/json", "https://httpbin.org/headers"], 
         "Custom headers"),
        
        # POST requests
        (["web-fetch", "--method", "POST", "--data", '{"name":"John","age":30}', 
          "https://httpbin.org/post"], 
         "POST request with JSON data"),
        
        # Output to file
        (["web-fetch", "-o", "output.json", "--format", "json", 
          "https://httpbin.org/json"], 
         "Save output to file in JSON format"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)


def batch_processing_examples() -> None:
    """Demonstrate batch processing via CLI."""
    print("\n" + "="*80)
    print("BATCH PROCESSING EXAMPLES")
    print("="*80)
    
    # Create a sample URLs file
    urls_file = Path("sample_urls.txt")
    urls_content = """https://httpbin.org/get
https://httpbin.org/json
https://httpbin.org/user-agent
https://httpbin.org/headers
https://httpbin.org/status/200"""
    
    urls_file.write_text(urls_content)
    print(f"Created sample URLs file: {urls_file}")
    
    examples = [
        # Basic batch processing
        (["web-fetch", "--batch", str(urls_file)], 
         "Batch fetch from URLs file"),
        
        (["web-fetch", "--batch", str(urls_file), "--concurrent", "3"], 
         "Batch fetch with custom concurrency limit"),
        
        (["web-fetch", "--batch", str(urls_file), "--format", "summary"], 
         "Batch fetch with summary output format"),
        
        (["web-fetch", "--batch", str(urls_file), "--retries", "2", 
          "--timeout", "15"], 
         "Batch fetch with retry and timeout configuration"),
        
        # Multiple URLs directly
        (["web-fetch", "https://httpbin.org/get", "https://httpbin.org/json", 
          "https://httpbin.org/user-agent"], 
         "Multiple URLs as arguments"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)
    
    # Cleanup
    urls_file.unlink(missing_ok=True)


def streaming_examples() -> None:
    """Demonstrate streaming and download features via CLI."""
    print("\n" + "="*80)
    print("STREAMING AND DOWNLOAD EXAMPLES")
    print("="*80)
    
    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)
    
    examples = [
        # Basic streaming download
        (["web-fetch", "--stream", "-o", "downloads/test_file.bin", 
          "https://httpbin.org/bytes/1024"], 
         "Stream download to file"),
        
        (["web-fetch", "--stream", "--progress", "--chunk-size", "4096", 
          "-o", "downloads/large_file.bin", "https://httpbin.org/bytes/10240"], 
         "Stream download with progress bar and custom chunk size"),
        
        (["web-fetch", "--stream", "--max-file-size", "1048576", 
          "-o", "downloads/limited_file.bin", "https://httpbin.org/bytes/2048"], 
         "Stream download with file size limit (1MB)"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)


def caching_examples() -> None:
    """Demonstrate caching features via CLI."""
    print("\n" + "="*80)
    print("CACHING EXAMPLES")
    print("="*80)
    
    examples = [
        # Basic caching
        (["web-fetch", "--cache", "https://httpbin.org/json"], 
         "Enable response caching (first request)"),
        
        (["web-fetch", "--cache", "https://httpbin.org/json"], 
         "Cached request (should be faster)"),
        
        (["web-fetch", "--cache", "--cache-ttl", "60", 
          "https://httpbin.org/get"], 
         "Custom cache TTL (60 seconds)"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)


def url_utilities_examples() -> None:
    """Demonstrate URL validation and normalization via CLI."""
    print("\n" + "="*80)
    print("URL UTILITIES EXAMPLES")
    print("="*80)
    
    examples = [
        # URL validation and normalization
        (["web-fetch", "--validate-urls", "--normalize-urls", 
          "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1"], 
         "URL validation and normalization"),
        
        (["web-fetch", "--validate-urls", "not-a-valid-url"], 
         "Invalid URL validation"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)


def crawler_examples() -> None:
    """Demonstrate crawler API features via CLI."""
    print("\n" + "="*80)
    print("CRAWLER API EXAMPLES")
    print("="*80)
    
    print("Note: These examples require API keys to be configured.")
    print("Set environment variables: FIRECRAWL_API_KEY, SPIDER_API_KEY, TAVILY_API_KEY")
    
    examples = [
        # Basic crawler usage
        (["web-fetch", "--use-crawler", "https://example.com"], 
         "Basic web scraping with crawler APIs"),
        
        (["web-fetch", "--use-crawler", "--crawler-type", "firecrawl", 
          "https://example.com"], 
         "Use specific crawler (Firecrawl)"),
        
        # Website crawling
        (["web-fetch", "--use-crawler", "--crawler-operation", "crawl", 
          "--max-pages", "5", "https://example.com"], 
         "Website crawling with page limit"),
        
        # Web search
        (["web-fetch", "--crawler-operation", "search", 
          "--search-query", "Python web scraping tutorials"], 
         "Web search using crawler APIs"),
        
        # Crawler status
        (["web-fetch", "--crawler-status"], 
         "Check crawler API status and configuration"),
    ]
    
    for cmd, desc in examples:
        print(f"\nExample: {desc}")
        print(f"Command: {' '.join(cmd)}")
        print("(Skipped - requires API keys)")


def advanced_configuration_examples() -> None:
    """Demonstrate advanced CLI configuration options."""
    print("\n" + "="*80)
    print("ADVANCED CONFIGURATION EXAMPLES")
    print("="*80)
    
    examples = [
        # SSL and security options
        (["web-fetch", "--no-verify-ssl", "https://self-signed.badssl.com/"], 
         "Disable SSL verification (use with caution)"),
        
        # Verbose output
        (["web-fetch", "-v", "--format", "detailed", 
          "https://httpbin.org/get"], 
         "Verbose output with detailed format"),
        
        # Complex configuration
        (["web-fetch", "--concurrent", "2", "--retries", "3", 
          "--timeout", "20", "--headers", "User-Agent: WebFetch-CLI/1.0", 
          "--format", "json", "-v", "https://httpbin.org/delay/1"], 
         "Complex configuration with multiple options"),
    ]
    
    for cmd, desc in examples:
        run_command(cmd, desc)


def main() -> None:
    """Run all CLI examples."""
    print("Web-Fetch CLI Comprehensive Examples")
    print("="*80)
    print("This script demonstrates all CLI features with practical examples.")
    print("Copy and paste these commands to try them yourself!")
    
    try:
        basic_http_examples()
        batch_processing_examples()
        streaming_examples()
        caching_examples()
        url_utilities_examples()
        crawler_examples()
        advanced_configuration_examples()
        
        print("\n" + "="*80)
        print("CLI EXAMPLES COMPLETED")
        print("="*80)
        print("All examples have been demonstrated!")
        print("For more help, run: web-fetch --help")
        
    except KeyboardInterrupt:
        print("\nExamples interrupted by user")
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    main()
