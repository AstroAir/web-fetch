# CLI Tools Overview

WebFetch provides powerful command-line interfaces for web content fetching, with both basic and enhanced formatting options.

## Available Commands

WebFetch includes two main CLI commands:

### `web-fetch` - Main CLI

The primary command-line interface with integrated enhanced formatting:

```bash
web-fetch [OPTIONS] URL
```

### `web-fetch-extended` - Extended CLI

Advanced CLI for specialized operations:

```bash
web-fetch-extended [COMMAND] [OPTIONS]
```

## Basic Usage

### Simple Requests

```bash
# Fetch a URL as text
web-fetch https://httpbin.org/json

# Fetch as specific content type
web-fetch -t json https://httpbin.org/json
web-fetch -t html https://example.com
web-fetch -t raw https://httpbin.org/bytes/1024
```

### Output Options

```bash
# Save to file
web-fetch -o results.json https://httpbin.org/json

# Different output formats
web-fetch --format json https://httpbin.org/json
web-fetch --format summary https://httpbin.org/json
web-fetch --format detailed https://httpbin.org/json
```

### HTTP Methods

```bash
# GET request (default)
web-fetch https://httpbin.org/get

# POST request with data
web-fetch --method POST --data '{"key":"value"}' https://httpbin.org/post

# PUT request
web-fetch --method PUT --data '{"update":"data"}' https://httpbin.org/put

# Custom headers
web-fetch --headers "Authorization: Bearer token" https://api.example.com
web-fetch --headers "Content-Type: application/json" --headers "X-API-Key: key" https://api.example.com
```

## Batch Operations

### Batch from File

```bash
# Create a file with URLs
echo "https://httpbin.org/get" > urls.txt
echo "https://httpbin.org/json" >> urls.txt
echo "https://httpbin.org/html" >> urls.txt

# Fetch all URLs
web-fetch --batch urls.txt

# With custom concurrency
web-fetch --batch urls.txt --concurrent 5

# Save batch results
web-fetch --batch urls.txt -o batch_results.json --format json
```

### Batch Configuration

```bash
# Control concurrency
web-fetch --batch urls.txt --concurrent 10

# Set timeouts
web-fetch --batch urls.txt --timeout 30

# Configure retries
web-fetch --batch urls.txt --retries 3
```

## File Operations

### Downloads

```bash
# Simple download
web-fetch https://httpbin.org/bytes/1048576 -o large_file.bin

# Streaming download with progress
web-fetch --stream --progress https://httpbin.org/bytes/1048576 -o large_file.bin

# Custom chunk size
web-fetch --stream --chunk-size 16384 https://example.com/file.zip -o file.zip

# Maximum file size limit
web-fetch --stream --max-file-size 10485760 https://example.com/file.zip -o file.zip
```

### Upload Operations

```bash
# File upload (using extended CLI)
web-fetch-extended upload --file document.pdf https://httpbin.org/post

# Multiple file upload
web-fetch-extended upload --file file1.txt --file file2.txt https://httpbin.org/post
```

## Advanced Features

### Caching

```bash
# Enable caching
web-fetch --cache https://api.example.com/data

# Custom cache TTL
web-fetch --cache --cache-ttl 600 https://api.example.com/data

# Cache status in output
web-fetch --cache --verbose https://api.example.com/data
```

### URL Utilities

```bash
# Validate URLs
web-fetch --validate-urls https://example.com

# Normalize URLs
web-fetch --normalize-urls "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1"

# Both validation and normalization
web-fetch --validate-urls --normalize-urls "https://EXAMPLE.COM/PATH"
```

### SSL and Security

```bash
# Disable SSL verification (not recommended for production)
web-fetch --no-verify-ssl https://self-signed.example.com

# Custom SSL configuration
web-fetch --verify-ssl https://secure.example.com
```

## Enhanced CLI Features

When the `rich` library is installed, WebFetch provides enhanced formatting:

### Visual Enhancements

- 🎨 **Colored Output** - Success (green), errors (red), warnings (yellow), info (blue)
- 📊 **Progress Bars** - Visual progress for batch operations and downloads
- 📋 **Formatted Tables** - Beautiful tables for structured data display
- 🎯 **Status Indicators** - Spinners and status messages for operations
- 🖼️ **Panels and Layouts** - Organized information display
- 🌈 **Syntax Highlighting** - JSON, HTML, and code formatting

### Installation for Enhanced Features

```bash
pip install rich>=13.0.0  # Optional for enhanced formatting
```

### Enhanced Examples

```bash
# Batch processing with enhanced progress bars
web-fetch --batch urls.txt --verbose --concurrent 10

# Download with progress indicator
web-fetch https://example.com/file.zip --download ./downloads/ --progress

# Crawler operations with enhanced status displays
web-fetch --use-crawler --crawler-type firecrawl https://example.com --format detailed
```

## Configuration Options

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type` | Content type (text, json, html, raw) | text |
| `-o, --output` | Output file path | stdout |
| `--format` | Output format (json, summary, detailed) | summary |
| `--timeout` | Request timeout in seconds | 30.0 |
| `--retries` | Maximum retry attempts | 3 |
| `--concurrent` | Maximum concurrent requests | 10 |
| `-v, --verbose` | Enable verbose output | false |

### HTTP Options

| Option | Description |
|--------|-------------|
| `--method` | HTTP method (GET, POST, PUT, DELETE, etc.) |
| `--data` | Request data for POST/PUT requests |
| `--headers` | Custom headers (can be used multiple times) |
| `--no-verify-ssl` | Disable SSL certificate verification |

### Streaming Options

| Option | Description | Default |
|--------|-------------|---------|
| `--stream` | Use streaming mode for downloads | false |
| `--chunk-size` | Chunk size for streaming (bytes) | 8192 |
| `--progress` | Show progress bar for downloads | false |
| `--max-file-size` | Maximum file size for downloads (bytes) | unlimited |

### Caching Options

| Option | Description | Default |
|--------|-------------|---------|
| `--cache` | Enable response caching | false |
| `--cache-ttl` | Cache TTL in seconds | 300 |

### URL Utilities

| Option | Description |
|--------|-------------|
| `--validate-urls` | Validate URLs before fetching |
| `--normalize-urls` | Normalize URLs before fetching |

## Extended CLI Commands

The `web-fetch-extended` command provides specialized operations:

### Available Commands

```bash
# Test RSS feeds
web-fetch-extended test rss https://feeds.example.com/rss.xml

# Database operations
web-fetch-extended db query --config db-config.json "SELECT * FROM users"

# Cloud storage operations
web-fetch-extended storage list --provider aws --bucket my-bucket

# API testing
web-fetch-extended api test --auth oauth2 https://api.example.com/endpoint
```

## Error Handling

### Common Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Network error |
| 4 | Authentication error |
| 5 | File operation error |

### Error Output

```bash
# Verbose error information
web-fetch --verbose https://invalid-url.example.com

# JSON error format
web-fetch --format json https://httpbin.org/status/404
```

## Examples and Use Cases

For comprehensive CLI examples, see:

- **[CLI Examples](examples.md)** - Detailed command examples
- **[Rich Interface Guide](rich-interface.md)** - Enhanced formatting features
- **[Configuration Examples](../examples/configuration.md)** - Configuration patterns

## Getting Help

```bash
# General help
web-fetch --help

# Extended CLI help
web-fetch-extended --help

# Command-specific help
web-fetch-extended test --help
```

## Next Steps

- **[CLI Examples](examples.md)** - Comprehensive command examples
- **[Rich Interface](rich-interface.md)** - Enhanced formatting guide
- **[Configuration](../user-guide/configuration.md)** - CLI configuration options
