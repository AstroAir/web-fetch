# Extended Resource Types

This document describes the extended resource types added to web-fetch, including RSS/Atom feeds, authenticated APIs, database connections, and cloud storage services.

## Overview

The web-fetch library has been extended with four new resource types that follow the same unified component architecture:

- **RSS/Atom Feeds** - Parse and extract content from RSS and Atom feeds
- **Authenticated APIs** - Access APIs with OAuth, API keys, JWT, and other authentication methods
- **Database Connections** - Execute queries on PostgreSQL, MySQL, and MongoDB databases
- **Cloud Storage** - Interact with AWS S3, Google Cloud Storage, and Azure Blob Storage

All new resource types integrate seamlessly with the existing component system, providing consistent interfaces, caching, validation, and error handling.

## RSS/Atom Feeds

### Overview

The RSS component provides comprehensive support for parsing RSS and Atom feeds with automatic format detection, content extraction, and metadata parsing.

### Configuration

```python
from web_fetch.models.extended_resources import RSSConfig, FeedFormat

rss_config = RSSConfig(
    format=FeedFormat.AUTO,  # Auto-detect RSS/Atom format
    max_items=50,            # Maximum items to parse
    include_content=True,    # Include full content in items
    validate_dates=True,     # Validate and parse dates
    follow_redirects=True,   # Follow HTTP redirects
    user_agent="MyApp/1.0"   # Custom User-Agent header
)
```

### Usage Examples

#### Basic Feed Parsing

```python
from web_fetch.convenience import fetch_rss_feed

# Fetch and parse RSS feed
result = await fetch_rss_feed(
    "https://example.com/feed.xml",
    max_items=20,
    include_content=True
)

if result.is_success:
    feed_data = result.content
    print(f"Feed title: {feed_data['title']}")
    print(f"Description: {feed_data['description']}")
    print(f"Items: {len(feed_data['items'])}")
    
    for item in feed_data['items']:
        print(f"- {item['title']}: {item['link']}")
```

#### Using Component Directly

```python
from web_fetch.components.rss_component import RSSComponent
from web_fetch.models.resource import ResourceRequest, ResourceKind
from pydantic import AnyUrl

component = RSSComponent(rss_config=rss_config)

request = ResourceRequest(
    uri=AnyUrl("https://example.com/feed.xml"),
    kind=ResourceKind.RSS
)

result = await component.fetch(request)
validated_result = await component.validate(result)
```

### Feed Metadata

The RSS component extracts comprehensive metadata:

```python
metadata = result.metadata['feed_metadata']
print(f"Feed type: {metadata['feed_type']}")
print(f"Version: {metadata['version']}")
print(f"Last updated: {metadata['last_build_date']}")
print(f"Language: {metadata['language']}")
print(f"Copyright: {metadata['copyright']}")
```

## Authenticated APIs

### Overview

The Authenticated API component extends HTTP functionality with integrated authentication support for multiple authentication methods.

### Supported Authentication Methods

- **OAuth 2.0** - Client credentials, authorization code flows
- **API Keys** - Header, query parameter, or body placement
- **JWT Tokens** - Token validation and refresh
- **Basic Authentication** - Username/password
- **Bearer Tokens** - Simple token authentication

### Configuration

```python
from web_fetch.models.extended_resources import AuthenticatedAPIConfig

# OAuth 2.0 Configuration
oauth_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={
        "token_url": "https://api.example.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "grant_type": "client_credentials",
        "scope": "read write"
    },
    retry_on_auth_failure=True,
    refresh_token_threshold=300,  # Refresh 5 minutes before expiry
    base_headers={"User-Agent": "MyApp/1.0"}
)

# API Key Configuration
api_key_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={
        "api_key": "your-api-key",
        "key_name": "X-API-Key",
        "location": "header"
    }
)
```

### Usage Examples

#### OAuth 2.0 API Access

```python
from web_fetch.convenience import fetch_authenticated_api

result = await fetch_authenticated_api(
    "https://api.example.com/data",
    auth_method="oauth2",
    auth_config={
        "token_url": "https://api.example.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "grant_type": "client_credentials"
    },
    method="GET",
    headers={"Accept": "application/json"}
)

if result.is_success:
    api_data = result.content
    print(f"API Response: {api_data}")
```

#### API Key Authentication

```python
result = await fetch_authenticated_api(
    "https://api.example.com/users",
    auth_method="api_key",
    auth_config={
        "api_key": "your-api-key",
        "key_name": "Authorization",
        "location": "header",
        "prefix": "Bearer"
    },
    method="POST",
    data={"name": "John Doe", "email": "john@example.com"}
)
```

#### JWT Token Authentication

```python
result = await fetch_authenticated_api(
    "https://api.example.com/protected",
    auth_method="jwt",
    auth_config={
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "header_name": "Authorization"
    }
)
```

### Authentication Metadata

```python
auth_metadata = result.metadata['authentication']
print(f"Auth method: {auth_metadata['method']}")
print(f"Authenticated: {auth_metadata['authenticated']}")
print(f"Retry attempted: {auth_metadata['retry_attempted']}")
```

## Database Connections

### Overview

The Database component provides async database connectivity for PostgreSQL, MySQL, and MongoDB with connection pooling and query execution.

### Supported Databases

- **PostgreSQL** - Using asyncpg driver
- **MySQL** - Using aiomysql driver  
- **MongoDB** - Using motor driver

### Configuration

```python
from web_fetch.models.extended_resources import DatabaseConfig, DatabaseType

# PostgreSQL Configuration
pg_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="myapp",
    username="user",
    password="password",
    min_connections=1,
    max_connections=10,
    connection_timeout=30.0,
    query_timeout=60.0,
    ssl_mode="prefer"
)

# MongoDB Configuration
mongo_config = DatabaseConfig(
    database_type=DatabaseType.MONGODB,
    host="localhost",
    port=27017,
    database="myapp",
    username="user",
    password="password",
    extra_params={
        "authSource": "admin",
        "ssl": True
    }
)
```

### Usage Examples

#### PostgreSQL Queries

```python
from web_fetch.convenience import execute_database_query

result = await execute_database_query(
    "postgresql://localhost:5432/myapp",
    "SELECT id, name, email FROM users WHERE active = $1",
    pg_config,
    parameters={"$1": True},
    fetch_mode="all",
    limit=100
)

if result.is_success:
    users = result.content['data']
    print(f"Found {len(users)} active users")
    for user in users:
        print(f"- {user['name']} ({user['email']})")
```

#### MongoDB Queries

```python
# MongoDB query as JSON
mongo_query = {
    "collection": "users",
    "operation": "find",
    "filter": {"status": "active"}
}

result = await execute_database_query(
    "mongodb://localhost:27017/myapp",
    json.dumps(mongo_query),
    mongo_config,
    limit=50
)
```

#### Using Component Directly

```python
from web_fetch.components.database_component import DatabaseComponent

async with DatabaseComponent(db_config=pg_config) as db:
    request = ResourceRequest(
        uri=AnyUrl("postgresql://localhost:5432/myapp"),
        kind=ResourceKind.DATABASE,
        options={
            "query": {
                "query": "SELECT COUNT(*) as total FROM users",
                "fetch_mode": "one"
            }
        }
    )
    
    result = await db.fetch(request)
    total_users = result.content['data']['total']
    print(f"Total users: {total_users}")
```

### Query Metadata

```python
db_metadata = result.metadata['database']
print(f"Database type: {db_metadata['type']}")
print(f"Host: {db_metadata['host']}")
print(f"Query type: {db_metadata['query_type']}")
print(f"Row count: {db_metadata['row_count']}")
```

## Cloud Storage

### Overview

The Cloud Storage component provides unified access to major cloud storage services with support for common operations like upload, download, list, and delete.

### Supported Providers

- **AWS S3** - Amazon Simple Storage Service
- **Google Cloud Storage** - Google Cloud Platform storage
- **Azure Blob Storage** - Microsoft Azure blob storage

### Configuration

```python
from web_fetch.models.extended_resources import CloudStorageConfig, CloudStorageProvider

# AWS S3 Configuration
s3_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="my-s3-bucket",
    access_key="AKIAIOSFODNN7EXAMPLE",
    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    region="us-east-1",
    multipart_threshold=8 * 1024 * 1024,  # 8MB
    max_concurrency=10,
    retry_attempts=3
)

# Google Cloud Storage Configuration
gcs_config = CloudStorageConfig(
    provider=CloudStorageProvider.GOOGLE_CLOUD,
    bucket_name="my-gcs-bucket",
    # GCS typically uses service account credentials
    extra_config={
        "credentials_path": "/path/to/service-account.json"
    }
)

# Azure Blob Storage Configuration
azure_config = CloudStorageConfig(
    provider=CloudStorageProvider.AZURE_BLOB,
    bucket_name="my-container",  # Container name in Azure
    access_key="mystorageaccount",  # Storage account name
    secret_key="account-key-here",  # Storage account key
    extra_config={
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=..."
    }
)
```

### Usage Examples

#### List Objects

```python
from web_fetch.convenience import cloud_storage_operation

# List all objects with a prefix
result = await cloud_storage_operation(
    "s3://my-bucket",
    "list",
    s3_config,
    prefix="documents/"
)

if result.is_success:
    objects = result.content['objects']
    print(f"Found {len(objects)} objects:")
    for obj in objects:
        print(f"- {obj['key']} ({obj['size']} bytes)")
```

#### Download File

```python
# Download a file from cloud storage
result = await cloud_storage_operation(
    "s3://my-bucket",
    "get",
    s3_config,
    key="documents/report.pdf",
    local_path="./downloads/report.pdf"
)

if result.is_success:
    file_info = result.content
    print(f"Downloaded: {file_info['key']}")
    print(f"Size: {file_info['size']} bytes")
    print(f"Content type: {file_info['content_type']}")
```

#### Upload File

```python
# Upload a file to cloud storage
result = await cloud_storage_operation(
    "s3://my-bucket",
    "put",
    s3_config,
    key="uploads/new-document.pdf",
    local_path="./local-file.pdf",
    content_type="application/pdf",
    metadata={"author": "John Doe", "version": "1.0"}
)

if result.is_success:
    print(f"Uploaded successfully: {result.content['key']}")
```

#### Delete Object

```python
# Delete an object from cloud storage
result = await cloud_storage_operation(
    "s3://my-bucket",
    "delete",
    s3_config,
    key="old-file.txt"
)

if result.is_success:
    print(f"Deleted: {result.content['key']}")
```

### Storage Metadata

```python
storage_metadata = result.metadata['cloud_storage']
print(f"Provider: {storage_metadata['provider']}")
print(f"Bucket: {storage_metadata['bucket']}")
print(f"Operation: {storage_metadata['operation']}")
print(f"Region: {storage_metadata['region']}")
```

## Unified Resource Manager

All extended resource types work seamlessly with the unified ResourceManager:

```python
from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceRequest, ResourceKind

manager = ResourceManager()

# List all available components
components = manager.list_components()
print("Available components:", components)

# Use any resource type through the manager
rss_request = ResourceRequest(
    uri=AnyUrl("https://example.com/feed.xml"),
    kind=ResourceKind.RSS
)

api_request = ResourceRequest(
    uri=AnyUrl("https://api.example.com/data"),
    kind=ResourceKind.API_AUTH,
    options={"auth_method": "api_key", "auth_config": {...}}
)

# Fetch using unified interface
rss_result = await manager.fetch(rss_request)
api_result = await manager.fetch(api_request)
```

## Error Handling

All extended components provide consistent error handling:

```python
result = await fetch_rss_feed("https://invalid-feed.com/feed.xml")

if not result.is_success:
    print(f"Error: {result.error}")
    print(f"Status code: {result.status_code}")

    # Check specific error types
    if "RSS feed fetch error" in result.error:
        print("Feed parsing failed")
    elif result.status_code == 404:
        print("Feed not found")
    elif result.status_code == 403:
        print("Access denied")
```

## Caching

All extended resource types support caching through the unified configuration:

```python
from web_fetch.models.resource import ResourceConfig

# Enable caching with custom TTL
config = ResourceConfig(
    enable_cache=True,
    cache_ttl_seconds=600,  # 10 minutes
    trace_id="my-request-123"
)

# Use with any resource type
result = await fetch_rss_feed(
    "https://example.com/feed.xml",
    config=config
)

# Cache key is automatically generated based on resource type and parameters
```

## Best Practices

### Security

1. **Store credentials securely** - Use environment variables or secure credential stores
2. **Use least privilege** - Grant minimal required permissions for database and cloud storage access
3. **Validate inputs** - Always validate URLs, queries, and file paths
4. **Enable SSL/TLS** - Use encrypted connections for all external services

### Performance

1. **Use connection pooling** - Configure appropriate pool sizes for database connections
2. **Enable caching** - Cache frequently accessed resources with appropriate TTLs
3. **Limit result sets** - Use pagination and limits for large datasets
4. **Monitor timeouts** - Set appropriate timeouts for different resource types

### Error Handling

1. **Check result status** - Always check `result.is_success` before using content
2. **Handle specific errors** - Implement specific handling for different error types
3. **Use retries** - Enable automatic retries for transient failures
4. **Log errors** - Implement comprehensive logging for debugging

### Resource Management

1. **Use context managers** - Use `async with` for database components
2. **Clean up connections** - Properly close database and storage connections
3. **Monitor resource usage** - Track connection pools and storage usage
4. **Implement circuit breakers** - Prevent cascading failures with circuit breaker patterns
