# CLI Interfaces Documentation

## Main CLI (web_fetch.cli.main)

### Entry Points
- `web-fetch` command (setuptools entry point)
- `python -m web_fetch.cli.main`
- Direct execution: `python web_fetch/cli/main.py`

### Command Structure
```
web-fetch [OPTIONS] [URLS...]
web-fetch [OPTIONS] COMMAND [ARGS...]
```

### Positional Arguments
- `urls` (nargs="*") - URLs to fetch (or use --batch for file input)

### Basic Options
- `-t, --type` {text,json,html,raw} - Content type for parsing (default: text)
- `--batch PATH` - File containing URLs to fetch (one per line)
- `-o, --output PATH` - Output file for results (default: stdout)
- `--format` {json,summary,detailed} - Output format (default: summary)

### Request Configuration
- `--method` - HTTP method (default: GET)
- `--data` - Request data (for POST/PUT requests)
- `--headers` - Custom headers in format "Key: Value" (can be used multiple times)

### Timing and Concurrency
- `--timeout FLOAT` - Request timeout in seconds (default: 30)
- `--concurrent INT` - Maximum concurrent requests (default: 10)
- `--retries INT` - Maximum retry attempts (default: 3)

### SSL and Verification
- `--no-verify-ssl` - Disable SSL certificate verification

### Streaming Options
- `--stream` - Use streaming mode for downloads
- `--chunk-size INT` - Chunk size for streaming (default: 8192 bytes)
- `--progress` - Show progress bar for downloads
- `--max-file-size INT` - Maximum file size for downloads (bytes)

### Caching Options
- `--cache` - Enable response caching
- `--cache-ttl INT` - Cache TTL in seconds (default: 300)

### URL Utilities
- `--validate-urls` - Validate URLs before fetching
- `--normalize-urls` - Normalize URLs before fetching

### Crawler API Options
- `--use-crawler` - Use crawler APIs instead of standard HTTP fetching
- `--crawler-type` {firecrawl,spider,tavily,anycrawl} - Specific crawler API to use
- `--crawler-operation` {scrape,crawl,search,extract} - Crawler operation type (default: scrape)
- `--search-query` - Search query (for search operations)
- `--max-pages INT` - Maximum pages to crawl
- `--max-depth INT` - Maximum crawl depth
- `--crawler-status` - Show crawler API status and exit

### Output Options
- `-v, --verbose` - Enable verbose output

### Subcommands
- `components` - Unified components interface (HTTP/FTP/GraphQL/WebSocket/etc.)

## Components Subcommand

### Command Structure
```
web-fetch components URI --kind KIND [OPTIONS]
```

### Required Arguments
- `uri` - Target resource URI
- `--kind` {http,ftp,graphql,websocket,etc.} - Resource kind (required)

### Optional Arguments
- `--options` - JSON string of type-specific options (default: "{}")
- `--headers` - JSON of headers (default: "{}")
- `--params` - JSON of params (default: "{}")
- `--timeout FLOAT` - Timeout override seconds
- `--format` {json,summary,detailed} - Output format (default: summary)
- `--verbose, -v` - Enable verbose output

## Extended CLI (web_fetch.cli.extended)

### Entry Points
- `web-fetch-extended` command (script)
- `python -m web_fetch.cli.extended`

### Global Options
- `--config, -c PATH` - Configuration file path
- `--verbose, -v` - Enable verbose output
- `--version` - Show version and exit

### Command Groups

#### Test Commands (`test`)
- `test rss` - Test RSS/Atom feed fetching
- `test database` - Test database connection
- `test cloud-storage` - Test cloud storage connection
- `test api` - Test authenticated API connection

#### Fetch Commands (`fetch`)
- `fetch rss` - Fetch RSS/Atom feeds
- `fetch database` - Execute database queries
- `fetch cloud-storage` - Perform cloud storage operations
- `fetch api` - Fetch from authenticated APIs

#### Cache Commands (`cache`)
- `cache clear` - Clear cache
- `cache stats` - Show cache statistics
- `cache config` - Configure cache settings

#### Monitor Commands (`monitor`)
- `monitor metrics` - Show metrics
- `monitor health` - Health check
- `monitor status` - Show status

#### Config Commands (`config`)
- `config validate` - Validate configuration
- `config show` - Show current configuration
- `config set` - Set configuration values

## Critical Behavior Requirements

### Exit Codes
- 0: Success
- 1: Error/failure
- Keyboard interrupt: Exit with message

### Output Formats
1. **JSON Format**: Complete structured data
2. **Summary Format**: Human-readable summary with key metrics
3. **Detailed Format**: Summary + content preview

### Error Handling
- Invalid URLs: Print error and exit(1)
- File not found: Print error and exit(1)
- Network errors: Print error with details
- Keyboard interrupt: Clean exit with message

### File Processing
- Batch files: One URL per line, ignore comments (#) and empty lines
- Output files: Write formatted results to specified file

### Progress Indicators
- Rich progress bars when available
- Fallback text indicators when Rich not available
- Verbose mode provides additional status information

## Compatibility Requirements

### Import Compatibility
- All existing import paths must continue to work
- Entry points must remain functional
- Module execution paths must be preserved

### Interface Compatibility
- All command-line arguments must work identically
- All output formats must produce identical results
- All error messages and exit codes must be preserved

### Behavioral Compatibility
- Argument parsing order and precedence
- Default values and validation rules
- File format expectations and processing
- Network behavior and retry logic
