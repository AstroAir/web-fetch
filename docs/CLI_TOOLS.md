# Web-Fetch CLI Tools

This document describes the command-line interface tools available for web-fetch, including both the standard CLI and the extended CLI for advanced resource types.

## Overview

Web-fetch provides two CLI tools:

1. **Standard CLI** (`web_fetch.cli.main`) - Basic HTTP fetching and crawling
2. **Extended CLI** (`web_fetch.cli.extended`) - Advanced resource types (RSS, Database, Cloud Storage, Authenticated APIs)

## Installation

To use the CLI tools, install web-fetch with the CLI dependencies:

```bash
# Basic installation
pip install web-fetch

# With extended resource types
pip install web-fetch[extended]

# Development installation
pip install -e .[extended]
```

## Extended CLI Usage

The extended CLI provides advanced functionality for testing and managing extended resource types.

### Quick Start

```bash
# Run the extended CLI
python -m web_fetch.cli.extended --help

# Or use the convenience script
./scripts/webfetch-extended --help
```

### Command Structure

```
webfetch-extended [OPTIONS] COMMAND [ARGS]...

Options:
  --config, -c PATH    Configuration file path
  --verbose, -v        Enable verbose output
  --version           Show version and exit
  --help              Show help message

Commands:
  test        Test configurations and connections
  fetch       Fetch resources using extended types
  cache       Advanced cache management
  monitor     Monitoring and metrics operations
  config      Configuration management
```

## Testing Commands

### RSS Feed Testing

Test RSS/Atom feed connectivity and parsing:

```bash
# Basic RSS test
webfetch-extended test rss --url https://feeds.feedburner.com/TechCrunch

# Advanced RSS test with options
webfetch-extended test rss \
  --url https://rss.cnn.com/rss/edition.rss \
  --max-items 20 \
  --include-content \
  --verbose
```

**Options:**

- `--url, -u`: RSS feed URL (required)
- `--max-items, -m`: Maximum items to fetch (default: 10)
- `--include-content`: Include full content in items
- `--verbose, -v`: Show detailed output

### Database Testing

Test database connections across different database types:

```bash
# PostgreSQL test
webfetch-extended test database \
  --host localhost \
  --port 5432 \
  --database mydb \
  --username myuser \
  --type postgresql \
  --ssl

# MySQL test
webfetch-extended test database \
  --host mysql.example.com \
  --port 3306 \
  --database testdb \
  --username testuser \
  --type mysql

# MongoDB test
webfetch-extended test database \
  --host mongo.example.com \
  --port 27017 \
  --database testdb \
  --username testuser \
  --type mongodb

# Custom query test
webfetch-extended test database \
  --host localhost \
  --database mydb \
  --username myuser \
  --type postgresql \
  --query "SELECT COUNT(*) FROM users"
```

**Options:**

- `--host, -h`: Database host (required)
- `--port, -p`: Database port (default: 5432)
- `--database, -d`: Database name (required)
- `--username, -u`: Database username (required)
- `--password`: Database password (prompted securely)
- `--type`: Database type (postgresql, mysql, mongodb)
- `--query, -q`: Custom test query
- `--ssl`: Use SSL connection

### Cloud Storage Testing

Test cloud storage connections:

```bash
# AWS S3 test
webfetch-extended test storage \
  --provider s3 \
  --bucket my-bucket \
  --access-key AKIAIOSFODNN7EXAMPLE \
  --region us-west-2 \
  --prefix documents/

# Google Cloud Storage test
webfetch-extended test storage \
  --provider gcs \
  --bucket my-gcs-bucket \
  --access-key service-account-key \
  --region us-central1

# Azure Blob Storage test
webfetch-extended test storage \
  --provider azure \
  --bucket my-container \
  --access-key mystorageaccount
```

**Options:**

- `--provider`: Cloud provider (s3, gcs, azure) (required)
- `--bucket, -b`: Bucket/container name (required)
- `--access-key`: Access key/account name (required)
- `--secret-key`: Secret key/account key (prompted securely)
- `--region, -r`: Region (for S3/GCS)
- `--prefix, -p`: Prefix to list objects

## Fetching Commands

### RSS Feed Fetching

Fetch RSS feeds with advanced options:

```bash
# Basic RSS fetch
webfetch-extended fetch rss https://feeds.feedburner.com/TechCrunch

# Advanced RSS fetch with output
webfetch-extended fetch rss \
  https://rss.cnn.com/rss/edition.rss \
  --max-items 50 \
  --output news.json \
  --format json \
  --include-content \
  --verbose

# CSV output
webfetch-extended fetch rss \
  https://feeds.bbci.co.uk/news/rss.xml \
  --output news.csv \
  --format csv \
  --max-items 100
```

**Options:**

- `--max-items, -m`: Maximum items to fetch (default: 20)
- `--output, -o`: Output file path
- `--format`: Output format (json, csv)
- `--include-content`: Include full content
- `--verbose, -v`: Show detailed output

## Cache Management

### Cache Statistics

View cache performance and statistics:

```bash
# Memory cache stats
webfetch-extended cache stats

# Redis cache stats
webfetch-extended cache stats --backend redis
```

**Options:**

- `--backend`: Cache backend (memory, redis)

### Cache Invalidation

Invalidate cache entries by various criteria:

```bash
# Invalidate by tag
webfetch-extended cache invalidate --tag "host:example.com"

# Invalidate by host
webfetch-extended cache invalidate --host example.com

# Invalidate by resource kind
webfetch-extended cache invalidate --kind rss

# Multiple criteria
webfetch-extended cache invalidate \
  --host api.example.com \
  --kind http
```

**Options:**

- `--tag, -t`: Invalidate by tag
- `--host, -h`: Invalidate by host
- `--kind, -k`: Invalidate by resource kind (http, rss, database, cloud_storage)

## Monitoring Commands

### Monitoring Status

View comprehensive monitoring and metrics:

```bash
# Basic monitoring status
webfetch-extended monitor status

# Specific backend
webfetch-extended monitor status --backend prometheus
```

**Options:**

- `--backend`: Metrics backend (memory, console, prometheus)

## Configuration Examples

### Environment Variables

Set up environment variables for common configurations:

```bash
# Database configuration
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=myapp
export DB_USER=myuser
export DB_PASSWORD=mypassword

# AWS S3 configuration
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Redis configuration
export REDIS_URL=redis://localhost:6379
```

### Configuration File

Create a configuration file for complex setups:

```yaml
# config.yaml
database:
  host: localhost
  port: 5432
  database: myapp
  username: myuser
  password: mypassword
  type: postgresql
  ssl: true

cache:
  backend: redis
  redis_url: redis://localhost:6379
  default_ttl: 3600

monitoring:
  backend: prometheus
  enable_metrics: true
```

Use with CLI:

```bash
webfetch-extended --config config.yaml test database
```

## Advanced Usage

### Batch Operations

Combine multiple operations:

```bash
# Test multiple RSS feeds
for url in \
  "https://rss.cnn.com/rss/edition.rss" \
  "https://feeds.bbci.co.uk/news/rss.xml" \
  "https://feeds.feedburner.com/TechCrunch"
do
  echo "Testing: $url"
  webfetch-extended test rss --url "$url" --max-items 5
done
```

### Pipeline Integration

Use in CI/CD pipelines:

```bash
#!/bin/bash
# health-check.sh

# Test critical RSS feeds
webfetch-extended test rss --url https://company.com/rss || exit 1

# Test database connectivity
webfetch-extended test database \
  --host $DB_HOST \
  --database $DB_NAME \
  --username $DB_USER \
  --type postgresql || exit 1

# Check cache performance
webfetch-extended cache stats --backend redis

echo "All health checks passed!"
```

### Monitoring Integration

Set up monitoring dashboards:

```bash
# Export metrics for Prometheus
webfetch-extended monitor status --backend prometheus > metrics.txt

# Generate monitoring report
webfetch-extended monitor status --backend memory | \
  grep -E "(hit rate|error rate|requests)" > monitoring-report.txt
```

## Troubleshooting

### Common Issues

1. **Import Errors**

   ```bash
   # Install missing dependencies
   pip install web-fetch[extended]
   ```

2. **Connection Timeouts**

   ```bash
   # Increase timeout for database tests
   webfetch-extended test database --host slow-db.com --timeout 60
   ```

3. **Authentication Failures**

   ```bash
   # Verify credentials
   webfetch-extended test storage --provider s3 --bucket test-bucket --verbose
   ```

4. **Cache Issues**

   ```bash
   # Clear cache and retry
   webfetch-extended cache invalidate --kind rss
   ```

### Debug Mode

Enable verbose output for debugging:

```bash
webfetch-extended --verbose test rss --url https://example.com/feed.xml
```

### Log Files

Check log files for detailed error information:

```bash
# Enable structured logging
export WEBFETCH_LOG_LEVEL=DEBUG
webfetch-extended test database --host localhost
```

## Integration with Standard CLI

The extended CLI complements the standard web-fetch CLI:

```bash
# Standard HTTP fetching
python -m web_fetch.cli.main https://httpbin.org/json

# Extended RSS fetching
webfetch-extended fetch rss https://feeds.example.com/rss.xml

# Both can be used together in scripts
python -m web_fetch.cli.main --crawler https://example.com
webfetch-extended test database --host localhost
```

## Support

For additional help:

1. Use `--help` with any command for detailed options
2. Check the main documentation at `docs/`
3. Review examples in `examples/`
4. Report issues on the project repository

## Examples

See the `examples/` directory for comprehensive usage examples:

- `examples/rss_feed_aggregator.py` - RSS processing
- `examples/database_analytics.py` - Database operations
- `examples/cloud_storage_manager.py` - Cloud storage management
- `examples/comprehensive_integration.py` - Multi-resource integration
