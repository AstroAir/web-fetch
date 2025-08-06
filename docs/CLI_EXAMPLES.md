# CLI Usage Examples

This document provides comprehensive examples for using the web-fetch command-line interface. The CLI provides access to all library features through simple command-line arguments.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Content Types and Parsing](#content-types-and-parsing)
- [Batch Processing](#batch-processing)
- [Streaming and Downloads](#streaming-and-downloads)
- [Caching](#caching)
- [Crawler APIs](#crawler-apis)
- [URL Utilities](#url-utilities)
- [Advanced Configuration](#advanced-configuration)
- [Output Formats](#output-formats)
- [Error Handling](#error-handling)

## Basic Usage

### Simple GET Requests

```bash
# Basic GET request (returns as text)
web-fetch https://httpbin.org/get

# Fetch with custom timeout
web-fetch --timeout 30 https://httpbin.org/delay/5

# Fetch with custom headers
web-fetch --headers "User-Agent: MyApp/1.0" --headers "Accept: application/json" https://httpbin.org/headers

# Verbose output
web-fetch -v https://httpbin.org/get
```

### HTTP Methods

```bash
# POST request with JSON data
web-fetch --method POST --data '{"name":"John","age":30}' https://httpbin.org/post

# PUT request
web-fetch --method PUT --data '{"updated":"value"}' https://httpbin.org/put

# DELETE request
web-fetch --method DELETE https://httpbin.org/delete

# Custom HTTP method
web-fetch --method PATCH --data '{"field":"value"}' https://httpbin.org/patch
```

## Content Types and Parsing

### Different Content Types

```bash
# Parse as JSON (structured output)
web-fetch -t json https://httpbin.org/json

# Parse as HTML (extract structured data)
web-fetch -t html https://example.com

# Get raw bytes
web-fetch -t raw https://httpbin.org/bytes/1024

# Default text parsing
web-fetch -t text https://httpbin.org/html
```

### Content Type Examples

```bash
# JSON API endpoint
web-fetch -t json https://jsonplaceholder.typicode.com/posts/1

# HTML page with structured extraction
web-fetch -t html --format json https://news.ycombinator.com

# Binary file as raw bytes
web-fetch -t raw -o image.jpg https://httpbin.org/image/jpeg
```

## Batch Processing

### URL Files

```bash
# Create a URLs file
echo -e "https://httpbin.org/get\nhttps://httpbin.org/json\nhttps://httpbin.org/user-agent" > urls.txt

# Batch fetch from file
web-fetch --batch urls.txt

# Batch with custom concurrency
web-fetch --batch urls.txt --concurrent 5

# Batch with retries and timeout
web-fetch --batch urls.txt --retries 3 --timeout 15
```

### Multiple URLs

```bash
# Multiple URLs as arguments
web-fetch https://httpbin.org/get https://httpbin.org/json https://httpbin.org/user-agent

# Multiple URLs with different processing
web-fetch -t json https://httpbin.org/json https://jsonplaceholder.typicode.com/posts/1
```

### Batch Output Formats

```bash
# Summary format for batch results
web-fetch --batch urls.txt --format summary

# Detailed format with full results
web-fetch --batch urls.txt --format detailed

# JSON format for programmatic processing
web-fetch --batch urls.txt --format json -o results.json
```

## Streaming and Downloads

### Basic Streaming

```bash
# Stream download to file
web-fetch --stream -o large_file.zip https://example.com/large-file.zip

# Stream with progress bar
web-fetch --stream --progress -o download.bin https://httpbin.org/bytes/1048576

# Custom chunk size for streaming
web-fetch --stream --chunk-size 16384 -o file.dat https://httpbin.org/bytes/65536
```

### Download Configuration

```bash
# Set maximum file size limit
web-fetch --stream --max-file-size 10485760 -o limited.zip https://example.com/file.zip

# Stream with custom chunk size and progress
web-fetch --stream --progress --chunk-size 32768 -o big_file.bin https://httpbin.org/bytes/2097152

# Resume interrupted downloads (if supported by server)
web-fetch --stream --resume -o partial_file.zip https://example.com/large-file.zip
```

### Progress Tracking

```bash
# Enable progress bar for downloads
web-fetch --stream --progress -o movie.mp4 https://example.com/movie.mp4

# Combine streaming with verbose output
web-fetch --stream --progress -v -o data.csv https://example.com/dataset.csv
```

## Caching

### Basic Caching

```bash
# Enable response caching
web-fetch --cache https://httpbin.org/json

# Second request will be served from cache (much faster)
web-fetch --cache https://httpbin.org/json

# Custom cache TTL (time-to-live)
web-fetch --cache --cache-ttl 300 https://api.example.com/data
```

### Cache Configuration

```bash
# Cache with custom TTL (10 minutes)
web-fetch --cache --cache-ttl 600 https://api.example.com/slow-endpoint

# Cache for batch requests
web-fetch --cache --batch urls.txt

# Combine caching with other features
web-fetch --cache --cache-ttl 300 -t json --format summary https://api.example.com/data
```

## Crawler APIs

**Note:** Crawler features require API keys. Set environment variables:
```bash
export FIRECRAWL_API_KEY="fc-your-api-key"
export SPIDER_API_KEY="your-spider-api-key"
export TAVILY_API_KEY="tvly-your-api-key"
```

### Basic Web Scraping

```bash
# Use crawler APIs for enhanced scraping
web-fetch --use-crawler https://example.com

# Specify a particular crawler
web-fetch --use-crawler --crawler-type firecrawl https://example.com

# Scrape with JavaScript rendering
web-fetch --use-crawler --crawler-type spider https://spa-app.example.com
```

### Website Crawling

```bash
# Crawl entire website with page limit
web-fetch --use-crawler --crawler-operation crawl --max-pages 10 https://docs.python.org

# Crawl with depth limit
web-fetch --use-crawler --crawler-operation crawl --max-pages 20 --max-depth 3 https://example.com

# Crawl and save results
web-fetch --use-crawler --crawler-operation crawl --max-pages 5 -o crawl_results.json --format json https://blog.example.com
```

### Web Search

```bash
# Search the web using crawler APIs
web-fetch --crawler-operation search --search-query "Python web scraping best practices"

# Search with specific crawler
web-fetch --crawler-operation search --crawler-type tavily --search-query "machine learning tutorials"

# Search with result limit
web-fetch --crawler-operation search --search-query "React.js examples" --max-pages 10
```

### Crawler Status

```bash
# Check crawler API status and configuration
web-fetch --crawler-status

# Verbose crawler status
web-fetch --crawler-status -v
```

## URL Utilities

### URL Validation and Normalization

```bash
# Validate URLs before fetching
web-fetch --validate-urls https://example.com

# Normalize URLs
web-fetch --normalize-urls "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1"

# Combine validation and normalization
web-fetch --validate-urls --normalize-urls "HTTP://EXAMPLE.COM/Path/To/Resource"

# Validate multiple URLs
web-fetch --validate-urls https://example.com https://invalid-url not-a-url
```

## Advanced Configuration

### SSL and Security

```bash
# Disable SSL verification (use with caution)
web-fetch --no-verify-ssl https://self-signed.badssl.com/

# Custom SSL configuration with headers
web-fetch --no-verify-ssl --headers "Accept: application/json" https://untrusted-root.badssl.com/
```

### Retry and Timeout Configuration

```bash
# Custom retry configuration
web-fetch --retries 5 --timeout 30 https://httpbin.org/status/500

# Exponential backoff with retries
web-fetch --retries 3 --timeout 10 https://httpbin.org/delay/5

# No retries for fast failure
web-fetch --retries 0 --timeout 5 https://httpbin.org/status/404
```

### Complex Configurations

```bash
# Combine multiple advanced options
web-fetch \
  --concurrent 3 \
  --retries 2 \
  --timeout 20 \
  --headers "User-Agent: WebFetch-CLI/1.0" \
  --headers "Accept: application/json" \
  --cache \
  --cache-ttl 300 \
  --format json \
  -v \
  https://api.example.com/data

# Streaming with advanced configuration
web-fetch \
  --stream \
  --progress \
  --chunk-size 32768 \
  --max-file-size 104857600 \
  --retries 3 \
  --timeout 60 \
  -o large_download.zip \
  https://example.com/large-file.zip
```

## Output Formats

### Format Options

```bash
# JSON format (structured output)
web-fetch --format json https://httpbin.org/json

# Summary format (concise results)
web-fetch --format summary --batch urls.txt

# Detailed format (comprehensive information)
web-fetch --format detailed -v https://httpbin.org/get

# Default format (content only)
web-fetch https://httpbin.org/get
```

### Output to Files

```bash
# Save JSON output to file
web-fetch -o results.json --format json https://httpbin.org/json

# Save summary to file
web-fetch --batch urls.txt --format summary -o batch_summary.txt

# Save detailed results
web-fetch --format detailed -o detailed_results.json https://httpbin.org/get
```

## Error Handling

### Handling Different HTTP Status Codes

```bash
# Handle 404 errors gracefully
web-fetch https://httpbin.org/status/404

# Handle server errors with retries
web-fetch --retries 3 https://httpbin.org/status/500

# Handle timeouts
web-fetch --timeout 1 https://httpbin.org/delay/5
```

### Verbose Error Information

```bash
# Get detailed error information
web-fetch -v https://httpbin.org/status/500

# Combine verbose with retries for debugging
web-fetch -v --retries 2 https://httpbin.org/status/503
```

## Environment Variables

You can configure web-fetch using environment variables:

```bash
# Set default timeout
export WEB_FETCH_TIMEOUT=30

# Set default concurrent requests
export WEB_FETCH_CONCURRENT=5

# Set crawler API keys
export FIRECRAWL_API_KEY="fc-your-key"
export SPIDER_API_KEY="spider-key"
export TAVILY_API_KEY="tvly-key"

# Set primary crawler
export WEB_FETCH_PRIMARY_CRAWLER="firecrawl"
```

## Tips and Best Practices

1. **Use batch processing** for multiple URLs to improve performance
2. **Enable caching** for repeated requests to the same endpoints
3. **Set appropriate timeouts** based on expected response times
4. **Use streaming** for large files to avoid memory issues
5. **Validate URLs** before processing to catch errors early
6. **Use verbose mode** (`-v`) for debugging and detailed information
7. **Save results to files** for further processing or analysis
8. **Configure retries** for unreliable endpoints
9. **Use crawler APIs** for JavaScript-heavy sites or enhanced scraping
10. **Monitor progress** with `--progress` for long-running downloads
