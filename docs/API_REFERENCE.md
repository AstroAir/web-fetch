# API Reference - Extended Resource Types

This document provides comprehensive API reference documentation for all extended resource types in the web-fetch library.

## Table of Contents

- [RSS/Atom Feed Component](#rssatom-feed-component)
- [Authenticated API Component](#authenticated-api-component)
- [Database Component](#database-component)
- [Cloud Storage Component](#cloud-storage-component)
- [Configuration Models](#configuration-models)
- [Error Handling](#error-handling)

## RSS/Atom Feed Component

### `RSSComponent`

The RSS component handles RSS and Atom feed parsing with automatic format detection and content extraction.

#### Class Definition

```python
class RSSComponent(ResourceComponent):
    """Resource component for RSS/Atom feeds."""
    
    kind = ResourceKind.RSS
    
    def __init__(
        self, 
        config: Optional[ResourceConfig] = None, 
        rss_config: Optional[RSSConfig] = None,
        http_config: Optional[HTTPFetchConfig] = None
    ) -> None
```

#### Parameters

- **config** (`Optional[ResourceConfig]`): Base resource configuration for caching and validation
- **rss_config** (`Optional[RSSConfig]`): RSS-specific configuration options
- **http_config** (`Optional[HTTPFetchConfig]`): HTTP configuration for feed fetching

#### Methods

##### `fetch(request: ResourceRequest) -> ResourceResult`

Fetches and parses RSS/Atom feed content.

**Parameters:**

- `request` (`ResourceRequest`): Resource request with feed URL and options

**Returns:**

- `ResourceResult`: Parsed feed data with metadata

**Example:**

```python
from web_fetch.components.rss_component import RSSComponent
from web_fetch.models.resource import ResourceRequest, ResourceKind
from web_fetch.models.extended_resources import RSSConfig
from pydantic import AnyUrl

# Configure RSS component
rss_config = RSSConfig(
    max_items=20,
    include_content=True,
    validate_dates=True
)

component = RSSComponent(rss_config=rss_config)

# Create request
request = ResourceRequest(
    uri=AnyUrl("https://example.com/feed.xml"),
    kind=ResourceKind.RSS
)

# Fetch feed
result = await component.fetch(request)

if result.is_success:
    feed_data = result.content
    print(f"Feed title: {feed_data['title']}")
    print(f"Items: {len(feed_data['items'])}")
```

##### `validate(result: ResourceResult) -> ResourceResult`

Validates RSS feed result structure and content.

**Parameters:**

- `result` (`ResourceResult`): Resource result to validate

**Returns:**

- `ResourceResult`: Validated result with validation metadata

##### `cache_key(request: ResourceRequest) -> Optional[str]`

Generates cache key for RSS feed requests.

**Parameters:**

- `request` (`ResourceRequest`): Resource request

**Returns:**

- `Optional[str]`: Cache key string or None if caching disabled

#### Result Structure

The RSS component returns structured feed data:

```python
{
    "title": "Feed Title",
    "description": "Feed Description", 
    "link": "https://example.com",
    "language": "en-US",
    "last_build_date": "2024-01-01T12:00:00Z",
    "feed_type": "rss",
    "version": "2.0",
    "items": [
        {
            "title": "Item Title",
            "description": "Item Description",
            "link": "https://example.com/item1",
            "pub_date": "2024-01-01T10:00:00Z",
            "guid": "unique-id",
            "author": "Author Name",
            "categories": ["Category1", "Category2"]
        }
    ],
    "item_count": 10
}
```

#### Metadata

The component provides comprehensive metadata:

```python
result.metadata = {
    "feed_metadata": {
        "feed_type": "rss",
        "version": "2.0",
        "language": "en-US",
        "copyright": "Copyright Info",
        "last_build_date": "2024-01-01T12:00:00Z",
        "item_count": 25
    },
    "feed_items": [
        # Detailed item metadata
    ],
    "parser_config": {
        "format": "auto",
        "max_items": 20,
        "include_content": True,
        "validate_dates": True
    },
    "total_items": 25,
    "truncated": True
}
```

## Authenticated API Component

### `AuthenticatedAPIComponent`

The authenticated API component extends HTTP functionality with integrated authentication support.

#### Class Definition

```python
class AuthenticatedAPIComponent(HTTPResourceComponent):
    """Resource component for authenticated API endpoints."""
    
    kind = ResourceKind.API_AUTH
    
    def __init__(
        self, 
        config: Optional[ResourceConfig] = None,
        api_config: Optional[AuthenticatedAPIConfig] = None
    ) -> None
```

#### Parameters

- **config** (`Optional[ResourceConfig]`): Base resource configuration
- **api_config** (`Optional[AuthenticatedAPIConfig]`): Authentication configuration

#### Methods

##### `fetch(request: ResourceRequest) -> ResourceResult`

Fetches from authenticated API endpoints with automatic authentication.

**Parameters:**

- `request` (`ResourceRequest`): API request with endpoint and options

**Returns:**

- `ResourceResult`: API response with authentication metadata

**Example:**

```python
from web_fetch.components.authenticated_api_component import AuthenticatedAPIComponent
from web_fetch.models.extended_resources import AuthenticatedAPIConfig
from web_fetch.models.resource import ResourceRequest, ResourceKind
from pydantic import AnyUrl

# Configure API authentication
api_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={
        "token_url": "https://api.example.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "grant_type": "client_credentials",
        "scope": "read write"
    },
    retry_on_auth_failure=True,
    refresh_token_threshold=300
)

component = AuthenticatedAPIComponent(api_config=api_config)

# Create API request
request = ResourceRequest(
    uri=AnyUrl("https://api.example.com/data"),
    kind=ResourceKind.API_AUTH,
    headers={"Accept": "application/json"},
    options={"method": "GET"}
)

# Fetch with authentication
result = await component.fetch(request)

if result.is_success:
    api_data = result.content
    auth_info = result.metadata["authentication"]
    print(f"Authenticated: {auth_info['authenticated']}")
```

##### `validate(result: ResourceResult) -> ResourceResult`

Validates API response with authentication-specific checks.

#### Supported Authentication Methods

1. **OAuth 2.0**

   ```python
   auth_config = {
       "token_url": "https://api.example.com/oauth/token",
       "client_id": "client-id",
       "client_secret": "client-secret",
       "grant_type": "client_credentials",
       "scope": "read write"
   }
   ```

2. **API Key**

   ```python
   auth_config = {
       "api_key": "your-api-key",
       "key_name": "X-API-Key",
       "location": "header",
       "prefix": "Bearer"
   }
   ```

3. **JWT Token**

   ```python
   auth_config = {
       "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
       "header_name": "Authorization",
       "verify_signature": True
   }
   ```

4. **Basic Authentication**

   ```python
   auth_config = {
       "username": "your-username",
       "password": "your-password"
   }
   ```

5. **Bearer Token**

   ```python
   auth_config = {
       "token": "your-bearer-token",
       "header_name": "Authorization"
   }
   ```

#### Authentication Metadata

```python
result.metadata["authentication"] = {
    "method": "oauth2",
    "authenticated": True,
    "retry_attempted": False,
    "token_refreshed": True,
    "expires_at": "2024-01-01T13:00:00Z"
}
```

## Database Component

### `DatabaseComponent`

The database component provides async database connectivity for PostgreSQL, MySQL, and MongoDB.

#### Class Definition

```python
class DatabaseComponent(ResourceComponent):
    """Resource component for database connections and queries."""

    kind = ResourceKind.DATABASE

    def __init__(
        self,
        config: Optional[ResourceConfig] = None,
        db_config: Optional[DatabaseConfig] = None
    ) -> None
```

#### Parameters

- **config** (`Optional[ResourceConfig]`): Base resource configuration
- **db_config** (`Optional[DatabaseConfig]`): Database connection configuration

#### Methods

##### `fetch(request: ResourceRequest) -> ResourceResult`

Executes database queries with connection pooling.

**Parameters:**

- `request` (`ResourceRequest`): Database request with query configuration

**Returns:**

- `ResourceResult`: Query results with metadata

**Example:**

```python
from web_fetch.components.database_component import DatabaseComponent
from web_fetch.models.extended_resources import DatabaseConfig, DatabaseType, DatabaseQuery
from web_fetch.models.resource import ResourceRequest, ResourceKind
from pydantic import AnyUrl, SecretStr

# Configure database connection
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="myapp",
    username="user",
    password=SecretStr("password"),
    min_connections=1,
    max_connections=10,
    connection_timeout=30.0,
    query_timeout=60.0
)

component = DatabaseComponent(db_config=db_config)

# Create database request
query_config = DatabaseQuery(
    query="SELECT id, name, email FROM users WHERE active = $1",
    parameters={"$1": True},
    fetch_mode="all",
    limit=100
)

request = ResourceRequest(
    uri=AnyUrl("postgresql://localhost:5432/myapp"),
    kind=ResourceKind.DATABASE,
    options={"query": query_config.dict()}
)

# Execute query
result = await component.fetch(request)

if result.is_success:
    query_results = result.content
    print(f"Found {query_results['row_count']} users")
    for user in query_results['data']:
        print(f"- {user['name']} ({user['email']})")
```

##### `validate(result: ResourceResult) -> ResourceResult`

Validates database query results.

#### Supported Databases

1. **PostgreSQL** (using asyncpg)

   ```python
   db_config = DatabaseConfig(
       database_type=DatabaseType.POSTGRESQL,
       host="localhost",
       port=5432,
       database="myapp",
       username="user",
       password=SecretStr("password"),
       ssl_mode="prefer"
   )
   ```

2. **MySQL** (using aiomysql)

   ```python
   db_config = DatabaseConfig(
       database_type=DatabaseType.MYSQL,
       host="localhost",
       port=3306,
       database="myapp",
       username="user",
       password=SecretStr("password")
   )
   ```

3. **MongoDB** (using motor)

   ```python
   db_config = DatabaseConfig(
       database_type=DatabaseType.MONGODB,
       host="localhost",
       port=27017,
       database="myapp",
       username="user",
       password=SecretStr("password"),
       extra_params={
           "authSource": "admin",
           "ssl": True
       }
   )
   ```

#### Query Modes

- **all**: Fetch all results
- **one**: Fetch single result
- **many**: Fetch limited results

#### MongoDB Query Format

For MongoDB, queries should be JSON format:

```python
mongo_query = {
    "collection": "users",
    "operation": "find",
    "filter": {"status": "active", "age": {"$gte": 18}}
}

query_config = DatabaseQuery(
    query=json.dumps(mongo_query),
    limit=50
)
```

#### Result Structure

```python
{
    "data": [
        {"id": 1, "name": "John", "email": "john@example.com"},
        {"id": 2, "name": "Jane", "email": "jane@example.com"}
    ],
    "row_count": 2
}
```

#### Database Metadata

```python
result.metadata["database"] = {
    "type": "postgresql",
    "host": "localhost",
    "database": "myapp",
    "query_type": "all",
    "row_count": 2,
    "execution_time": 0.045
}
```

#### Context Manager Usage

```python
async with DatabaseComponent(db_config=db_config) as db:
    result = await db.fetch(request)
    # Connection automatically cleaned up
```

## Cloud Storage Component

### `CloudStorageComponent`

The cloud storage component provides unified access to AWS S3, Google Cloud Storage, and Azure Blob Storage.

#### Class Definition

```python
class CloudStorageComponent(ResourceComponent):
    """Resource component for cloud storage operations."""

    kind = ResourceKind.CLOUD_STORAGE

    def __init__(
        self,
        config: Optional[ResourceConfig] = None,
        storage_config: Optional[CloudStorageConfig] = None
    ) -> None
```

#### Parameters

- **config** (`Optional[ResourceConfig]`): Base resource configuration
- **storage_config** (`Optional[CloudStorageConfig]`): Cloud storage configuration

#### Methods

##### `fetch(request: ResourceRequest) -> ResourceResult`

Executes cloud storage operations.

**Parameters:**

- `request` (`ResourceRequest`): Storage request with operation configuration

**Returns:**

- `ResourceResult`: Operation results with metadata

**Example:**

```python
from web_fetch.components.cloud_storage_component import CloudStorageComponent
from web_fetch.models.extended_resources import (
    CloudStorageConfig, CloudStorageProvider, CloudStorageOperation
)
from web_fetch.models.resource import ResourceRequest, ResourceKind
from pydantic import AnyUrl, SecretStr

# Configure cloud storage
storage_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="my-bucket",
    access_key=SecretStr("AKIAIOSFODNN7EXAMPLE"),
    secret_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
    region="us-east-1"
)

component = CloudStorageComponent(storage_config=storage_config)

# List objects operation
list_operation = CloudStorageOperation(
    operation="list",
    prefix="documents/"
)

request = ResourceRequest(
    uri=AnyUrl("s3://my-bucket"),
    kind=ResourceKind.CLOUD_STORAGE,
    options={"operation": list_operation.dict()}
)

# Execute operation
result = await component.fetch(request)

if result.is_success:
    objects = result.content['objects']
    print(f"Found {len(objects)} objects:")
    for obj in objects:
        print(f"- {obj['key']} ({obj['size']} bytes)")
```

#### Supported Operations

1. **List Objects**

   ```python
   operation = CloudStorageOperation(
       operation="list",
       prefix="documents/",
   )
   ```

2. **Get Object**

   ```python
   operation = CloudStorageOperation(
       operation="get",
       key="documents/file.pdf"
   )
   ```

3. **Put Object**

   ```python
   operation = CloudStorageOperation(
       operation="put",
       key="uploads/new-file.pdf",
       local_path="./local-file.pdf",
       content_type="application/pdf",
       metadata={"author": "John Doe"}
   )
   ```

4. **Delete Object**

   ```python
   operation = CloudStorageOperation(
       operation="delete",
       key="old-file.txt"
   )
   ```

#### Supported Providers

1. **AWS S3**

   ```python
   storage_config = CloudStorageConfig(
       provider=CloudStorageProvider.AWS_S3,
       bucket_name="my-s3-bucket",
       access_key=SecretStr("access-key"),
       secret_key=SecretStr("secret-key"),
       region="us-east-1"
   )
   ```

2. **Google Cloud Storage**

   ```python
   storage_config = CloudStorageConfig(
       provider=CloudStorageProvider.GOOGLE_CLOUD,
       bucket_name="my-gcs-bucket",
       extra_config={
           "credentials_path": "/path/to/service-account.json"
       }
   )
   ```

3. **Azure Blob Storage**

   ```python
   storage_config = CloudStorageConfig(
       provider=CloudStorageProvider.AZURE_BLOB,
       bucket_name="my-container",
       access_key=SecretStr("storage-account-name"),
       secret_key=SecretStr("storage-account-key")
   )
   ```

#### Result Structures

**List Operation:**

```python
{
    "operation": "list",
    "prefix": "documents/",
    "objects": [
        {
            "key": "documents/file1.pdf",
            "size": 1024,
            "last_modified": "2024-01-01T12:00:00Z",
            "etag": "abc123"
        }
    ],
    "count": 1
}
```

**Get Operation:**

```python
{
    "operation": "get",
    "key": "documents/file.pdf",
    "content": b"binary-content",
    "content_type": "application/pdf",
    "size": 1024,
    "last_modified": "2024-01-01T12:00:00Z",
    "metadata": {"author": "John Doe"}
}
```

#### Storage Metadata

```python
result.metadata["cloud_storage"] = {
    "provider": "aws_s3",
    "bucket": "my-bucket",
    "operation": "list",
    "region": "us-east-1",
    "execution_time": 0.234
}
```

## Configuration Models

### `RSSConfig`

Configuration model for RSS/Atom feed parsing.

```python
class RSSConfig(BaseConfig):
    format: FeedFormat = FeedFormat.AUTO
    max_items: int = Field(default=50, ge=1, le=1000)
    include_content: bool = True
    validate_dates: bool = True
    follow_redirects: bool = True
    user_agent: Optional[str] = None
```

**Fields:**

- `format`: Feed format preference (RSS, ATOM, AUTO)
- `max_items`: Maximum items to parse (1-1000)
- `include_content`: Include full content in items
- `validate_dates`: Validate and parse dates
- `follow_redirects`: Follow HTTP redirects
- `user_agent`: Custom User-Agent header

### `AuthenticatedAPIConfig`

Configuration model for authenticated API access.

```python
class AuthenticatedAPIConfig(BaseConfig):
    auth_method: str
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    retry_on_auth_failure: bool = True
    refresh_token_threshold: int = Field(default=300, ge=0)
    base_headers: Dict[str, str] = Field(default_factory=dict)
```

**Fields:**

- `auth_method`: Authentication method (oauth2, api_key, jwt, basic, bearer)
- `auth_config`: Authentication configuration dictionary
- `retry_on_auth_failure`: Retry request on auth failure
- `refresh_token_threshold`: Seconds before expiry to refresh token
- `base_headers`: Base headers for all requests

### `DatabaseConfig`

Configuration model for database connections.

```python
class DatabaseConfig(BaseConfig):
    database_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    password: SecretStr
    min_connections: int = Field(default=1, ge=1)
    max_connections: int = Field(default=10, ge=1)
    connection_timeout: float = Field(default=30.0, gt=0)
    query_timeout: float = Field(default=60.0, gt=0)
    ssl_mode: Optional[str] = None
    extra_params: Dict[str, Any] = Field(default_factory=dict)
```

**Fields:**

- `database_type`: Type of database (POSTGRESQL, MYSQL, MONGODB)
- `host`: Database host
- `port`: Database port
- `database`: Database name
- `username`: Database username
- `password`: Database password (SecretStr)
- `min_connections`: Minimum connections in pool
- `max_connections`: Maximum connections in pool
- `connection_timeout`: Connection timeout in seconds
- `query_timeout`: Query timeout in seconds
- `ssl_mode`: SSL mode for connection
- `extra_params`: Additional connection parameters

### `CloudStorageConfig`

Configuration model for cloud storage services.

```python
class CloudStorageConfig(BaseConfig):
    provider: CloudStorageProvider
    bucket_name: str
    access_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None
    token: Optional[SecretStr] = None
    region: Optional[str] = None
    endpoint_url: Optional[str] = None
    multipart_threshold: int = Field(default=8 * 1024 * 1024, ge=1)
    max_concurrency: int = Field(default=10, ge=1)
    retry_attempts: int = Field(default=3, ge=0)
    extra_config: Dict[str, Any] = Field(default_factory=dict)
```

**Fields:**

- `provider`: Cloud storage provider (AWS_S3, GOOGLE_CLOUD, AZURE_BLOB)
- `bucket_name`: Storage bucket/container name
- `access_key`: Access key ID (SecretStr)
- `secret_key`: Secret access key (SecretStr)
- `token`: Session token (SecretStr)
- `region`: Storage region
- `endpoint_url`: Custom endpoint URL
- `multipart_threshold`: Multipart upload threshold in bytes
- `max_concurrency`: Maximum concurrent operations
- `retry_attempts`: Number of retry attempts
- `extra_config`: Additional provider configuration

## Error Handling

### Common Error Types

All components return consistent error information in the `ResourceResult.error` field:

#### RSS Component Errors

- `"RSS feed fetch error: Invalid XML content"` - Feed parsing failed
- `"RSS feed fetch error: Network timeout"` - Network connectivity issues
- `"Feed missing required title or description"` - Invalid feed structure

#### Authenticated API Component Errors

- `"Authentication failed: Invalid credentials"` - Authentication setup failed
- `"Authenticated API fetch error: Token expired"` - Token refresh needed
- `"API validation failed: Invalid response format"` - Response validation failed

#### Database Component Errors

- `"Database query error: Connection failed"` - Database connectivity issues
- `"Database query error: Invalid query syntax"` - SQL/query syntax errors
- `"Database validation failed: No results"` - Query returned no data

#### Cloud Storage Component Errors

- `"Cloud storage error: Invalid credentials"` - Authentication failed
- `"Cloud storage error: Bucket not found"` - Storage bucket doesn't exist
- `"Cloud storage error: Permission denied"` - Insufficient permissions

### Error Metadata

Components provide detailed error information in metadata:

```python
if not result.is_success:
    print(f"Error: {result.error}")
    print(f"Status code: {result.status_code}")

    # Component-specific error details
    if "authentication" in result.metadata:
        auth_error = result.metadata["authentication"]
        print(f"Auth method: {auth_error.get('method')}")
        print(f"Auth error: {auth_error.get('error')}")
```

### Best Practices

1. **Always check `result.is_success`** before accessing content
2. **Handle specific error types** with appropriate retry logic
3. **Log errors with context** for debugging
4. **Use timeouts** to prevent hanging operations
5. **Implement circuit breakers** for external service failures
