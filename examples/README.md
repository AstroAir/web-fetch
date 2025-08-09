# Web-Fetch Extended Resource Types Examples

This directory contains comprehensive examples demonstrating how to use web-fetch's extended resource types in real-world scenarios.

## 📁 Example Files

### 1. RSS Feed Aggregator (`rss_feed_aggregator.py`)
**Demonstrates:** RSS/Atom feed processing with advanced features

**Features:**
- Multiple RSS feed processing
- Content filtering and deduplication
- Error handling and retry logic
- Caching for performance
- Data export to JSON/CSV formats
- Category-based organization

**Usage:**
```bash
python examples/rss_feed_aggregator.py
```

**Key Concepts:**
- RSS configuration and optimization
- Concurrent feed processing
- Content validation and filtering
- Performance monitoring

### 2. API Data Collector (`api_data_collector.py`)
**Demonstrates:** Authenticated API access with multiple authentication methods

**Features:**
- OAuth 2.0 authentication
- API key authentication
- JWT token authentication
- Rate limiting and retry logic
- Data transformation and aggregation
- Comprehensive error handling

**Usage:**
```bash
# Set environment variables first
export GITHUB_CLIENT_ID="your_github_client_id"
export GITHUB_CLIENT_SECRET="your_github_client_secret"
export WEATHER_API_KEY="your_openweathermap_api_key"

python examples/api_data_collector.py
```

**Key Concepts:**
- Multi-method authentication
- API rate limiting strategies
- Data enrichment patterns
- Secure credential management

### 3. Database Analytics (`database_analytics.py`)
**Demonstrates:** Multi-database connectivity and analytics

**Features:**
- PostgreSQL, MySQL, and MongoDB support
- Complex analytical queries
- Connection pooling optimization
- Cross-database analytics
- Performance monitoring

**Usage:**
```bash
# Configure database connections
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="analytics"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="password"

python examples/database_analytics.py
```

**Key Concepts:**
- Multi-database architecture
- Query optimization strategies
- Connection pool management
- Analytics query patterns

### 4. Cloud Storage Manager (`cloud_storage_manager.py`)
**Demonstrates:** Multi-provider cloud storage operations

**Features:**
- AWS S3, Google Cloud Storage, Azure Blob support
- File upload, download, and listing
- Batch operations
- Cross-provider synchronization
- Metadata management

**Usage:**
```bash
# Configure cloud storage credentials
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_S3_BUCKET="your-bucket-name"
export AWS_REGION="us-east-1"

python examples/cloud_storage_manager.py
```

**Key Concepts:**
- Multi-provider abstraction
- Batch file operations
- Storage optimization strategies
- Cross-provider data migration

### 5. Comprehensive Integration (`comprehensive_integration.py`)
**Demonstrates:** Complete data pipeline integrating all resource types

**Features:**
- News aggregation pipeline
- RSS feeds → API enrichment → Database storage → Cloud archival
- Error handling and recovery
- Performance monitoring
- Pipeline orchestration

**Usage:**
```bash
# Configure all services
export DB_HOST="localhost"
export DB_PASSWORD="password"
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export S3_BUCKET="news-archive"

python examples/comprehensive_integration.py
```

**Key Concepts:**
- Multi-resource integration
- Data pipeline design
- Error recovery strategies
- End-to-end data processing

## 🚀 Getting Started

### Prerequisites

1. **Install web-fetch with extended dependencies:**
   ```bash
   pip install web-fetch[extended]
   ```

2. **Install additional dependencies for examples:**
   ```bash
   pip install asyncio pathlib
   ```

### Environment Setup

Each example requires specific environment variables. Create a `.env` file or export variables:

```bash
# Database Configuration
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="your_database"
export DB_USER="your_username"
export DB_PASSWORD="your_password"

# AWS S3 Configuration
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_S3_BUCKET="your-bucket"
export AWS_REGION="us-east-1"

# API Keys
export GITHUB_CLIENT_ID="your_github_client_id"
export GITHUB_CLIENT_SECRET="your_github_client_secret"
export WEATHER_API_KEY="your_openweathermap_key"
```

### Running Examples

1. **Choose an example** based on your use case
2. **Configure environment variables** as needed
3. **Run the example:**
   ```bash
   python examples/example_name.py
   ```

## 📊 Example Output

Each example generates detailed output and exports results:

### RSS Feed Aggregator
- Console output with processing statistics
- `aggregated_feeds_TIMESTAMP.json` - Structured feed data
- `aggregated_feeds_TIMESTAMP.csv` - Tabular export

### API Data Collector
- Console output with collection summary
- `api_data_collection_TIMESTAMP.json` - Collected API data

### Database Analytics
- Console output with analysis results
- `database_analytics_TIMESTAMP.json` - Analytics results

### Cloud Storage Manager
- Console output with operation summary
- `storage_operations_TIMESTAMP.json` - Operations log

### Comprehensive Integration
- Console output with pipeline summary
- `pipeline_results_TIMESTAMP.json` - Complete pipeline results
- Database tables with processed data
- Cloud storage archives

## 🔧 Customization

### Modifying Examples

Each example is designed to be easily customizable:

1. **Change data sources:** Update URLs, API endpoints, or database queries
2. **Adjust processing logic:** Modify filtering, transformation, or enrichment
3. **Add new features:** Extend with additional APIs or storage providers
4. **Optimize performance:** Tune connection pools, batch sizes, or caching

### Configuration Options

Examples demonstrate various configuration patterns:

```python
# Performance-optimized configuration
resource_config = ResourceConfig(
    enable_cache=True,
    cache_ttl_seconds=1800,
    max_retries=3,
    timeout_seconds=30
)

# High-throughput database configuration
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    min_connections=5,
    max_connections=20,
    connection_timeout=10.0,
    query_timeout=60.0
)

# Secure cloud storage configuration
storage_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    multipart_threshold=16 * 1024 * 1024,
    max_concurrency=10,
    retry_attempts=3
)
```

## 🛠️ Troubleshooting

### Common Issues

1. **Import Errors:**
   ```bash
   pip install web-fetch[extended]
   ```

2. **Authentication Failures:**
   - Verify environment variables are set
   - Check credential validity
   - Review API documentation for requirements

3. **Connection Issues:**
   - Verify network connectivity
   - Check firewall settings
   - Validate connection parameters

4. **Performance Issues:**
   - Adjust connection pool sizes
   - Tune cache settings
   - Implement rate limiting

### Debug Mode

Enable debug logging in examples:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Additional Resources

- **[API Reference](../docs/API_REFERENCE.md)** - Complete API documentation
- **[Configuration Guide](../docs/CONFIGURATION_GUIDE.md)** - Detailed configuration options
- **[Troubleshooting Guide](../docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Security Best Practices](../docs/SECURITY.md)** - Security guidelines

## 🤝 Contributing

To contribute new examples:

1. Follow the existing code structure and documentation style
2. Include comprehensive error handling
3. Add configuration examples and environment variable documentation
4. Test with multiple scenarios and edge cases
5. Update this README with your example description

## 📄 License

These examples are provided under the same license as the web-fetch library (MIT License).
