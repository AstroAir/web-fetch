# Configuration Guide - Extended Resource Types

This guide provides detailed configuration information for all extended resource types, including all available options, their effects, and best practice recommendations.

## Table of Contents

- [RSS/Atom Feed Configuration](#rssatom-feed-configuration)
- [Authenticated API Configuration](#authenticated-api-configuration)
- [Database Configuration](#database-configuration)
- [Cloud Storage Configuration](#cloud-storage-configuration)
- [Base Resource Configuration](#base-resource-configuration)
- [Environment Variables](#environment-variables)
- [Configuration Validation](#configuration-validation)

## RSS/Atom Feed Configuration

### `RSSConfig` Options

The RSS configuration controls feed parsing behavior and content extraction.

#### Basic Configuration

```python
from web_fetch.models.extended_resources import RSSConfig, FeedFormat

# Minimal configuration
rss_config = RSSConfig()

# Custom configuration
rss_config = RSSConfig(
    format=FeedFormat.AUTO,
    max_items=50,
    include_content=True,
    validate_dates=True,
    follow_redirects=True,
    user_agent="MyApp/1.0"
)
```

#### Configuration Options

| Option | Type | Default | Description | Effect |
|--------|------|---------|-------------|--------|
| `format` | `FeedFormat` | `AUTO` | Feed format preference | Controls parser selection |
| `max_items` | `int` | `50` | Maximum items to parse (1-1000) | Limits memory usage and processing time |
| `include_content` | `bool` | `True` | Include full content in items | Affects response size and completeness |
| `validate_dates` | `bool` | `True` | Validate and parse dates | Ensures date consistency |
| `follow_redirects` | `bool` | `True` | Follow HTTP redirects | Handles moved feeds |
| `user_agent` | `Optional[str]` | `None` | Custom User-Agent header | May be required by some feeds |

#### Feed Format Options

```python
from web_fetch.models.extended_resources import FeedFormat

# Auto-detect format (recommended)
format=FeedFormat.AUTO

# Force RSS parsing
format=FeedFormat.RSS

# Force Atom parsing
format=FeedFormat.ATOM
```

#### Performance Considerations

- **max_items**: Lower values improve performance but may miss content
- **include_content**: Disabling reduces bandwidth and memory usage
- **validate_dates**: Disabling improves parsing speed but may cause date issues

#### Best Practices

```python
# Production configuration
rss_config = RSSConfig(
    format=FeedFormat.AUTO,          # Let parser auto-detect
    max_items=100,                   # Reasonable limit
    include_content=True,            # Full content extraction
    validate_dates=True,             # Ensure date consistency
    follow_redirects=True,           # Handle moved feeds
    user_agent="YourApp/1.0 (+https://yoursite.com/contact)"  # Identify your app
)

# High-performance configuration
rss_config = RSSConfig(
    max_items=25,                    # Limit for speed
    include_content=False,           # Metadata only
    validate_dates=False,            # Skip validation
    follow_redirects=False           # Direct access only
)
```

## Authenticated API Configuration

### `AuthenticatedAPIConfig` Options

The API configuration manages authentication methods and retry behavior.

#### Basic Configuration

```python
from web_fetch.models.extended_resources import AuthenticatedAPIConfig

# API Key authentication
api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={
        "api_key": "your-api-key",
        "key_name": "X-API-Key",
        "location": "header"
    }
)
```

#### Configuration Options

| Option | Type | Default | Description | Effect |
|--------|------|---------|-------------|--------|
| `auth_method` | `str` | Required | Authentication method | Determines auth strategy |
| `auth_config` | `Dict[str, Any]` | `{}` | Auth-specific configuration | Method-dependent settings |
| `retry_on_auth_failure` | `bool` | `True` | Retry on 401/403 errors | Improves reliability |
| `refresh_token_threshold` | `int` | `300` | Token refresh threshold (seconds) | Prevents token expiry |
| `base_headers` | `Dict[str, str]` | `{}` | Headers for all requests | Common request headers |

#### Authentication Methods

##### 1. OAuth 2.0 Configuration

```python
oauth_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={
        "token_url": "https://api.example.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "grant_type": "client_credentials",  # or "authorization_code"
        "scope": "read write",
        "audience": "https://api.example.com",  # Optional
        "resource": "https://api.example.com"   # Optional
    },
    retry_on_auth_failure=True,
    refresh_token_threshold=300,  # Refresh 5 minutes before expiry
    base_headers={
        "User-Agent": "MyApp/1.0",
        "Accept": "application/json"
    }
)
```

**OAuth 2.0 Options:**

- `token_url`: OAuth token endpoint
- `client_id`: OAuth client identifier
- `client_secret`: OAuth client secret
- `grant_type`: OAuth grant type (client_credentials, authorization_code)
- `scope`: Requested permissions
- `audience`: Token audience (optional)
- `resource`: Target resource (optional)

##### 2. API Key Configuration

```python
api_key_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={
        "api_key": "your-api-key",
        "key_name": "X-API-Key",        # Header/parameter name
        "location": "header",           # "header", "query", or "body"
        "prefix": "Bearer",             # Optional prefix
        "encoding": "base64"            # Optional encoding
    }
)
```

**API Key Options:**

- `api_key`: The API key value
- `key_name`: Name of header/parameter
- `location`: Where to place the key (header, query, body)
- `prefix`: Optional prefix (e.g., "Bearer", "Token")
- `encoding`: Optional encoding (base64, hex)

##### 3. JWT Token Configuration

```python
jwt_config = AuthenticatedAPIConfig(
    auth_method="jwt",
    auth_config={
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "header_name": "Authorization",
        "prefix": "Bearer",
        "verify_signature": True,
        "verify_expiry": True,
        "algorithm": "HS256",
        "secret": "your-secret-key"     # For verification
    }
)
```

**JWT Options:**

- `token`: JWT token string
- `header_name`: Authorization header name
- `prefix`: Token prefix (usually "Bearer")
- `verify_signature`: Verify token signature
- `verify_expiry`: Check token expiration
- `algorithm`: Signing algorithm
- `secret`: Secret key for verification

##### 4. Basic Authentication Configuration

```python
basic_config = AuthenticatedAPIConfig(
    auth_method="basic",
    auth_config={
        "username": "your-username",
        "password": "your-password",
        "encoding": "utf-8"             # Optional
    }
)
```

##### 5. Bearer Token Configuration

```python
bearer_config = AuthenticatedAPIConfig(
    auth_method="bearer",
    auth_config={
        "token": "your-bearer-token",
        "header_name": "Authorization"  # Optional, defaults to "Authorization"
    }
)
```

#### Retry and Refresh Settings

```python
# Conservative settings (high reliability)
api_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={...},
    retry_on_auth_failure=True,
    refresh_token_threshold=600,    # Refresh 10 minutes early
    base_headers={
        "User-Agent": "MyApp/1.0",
        "Accept": "application/json",
        "Cache-Control": "no-cache"
    }
)

# Aggressive settings (high performance)
api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={...},
    retry_on_auth_failure=False,    # No retries
    refresh_token_threshold=60,     # Minimal refresh window
    base_headers={}                 # Minimal headers
)
```

#### Best Practices

1. **Use environment variables** for sensitive credentials
2. **Set appropriate refresh thresholds** based on token lifetime
3. **Include User-Agent headers** to identify your application
4. **Enable retries** for production environments
5. **Use HTTPS** for all authentication endpoints

```python
import os

# Secure configuration using environment variables
api_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={
        "token_url": os.getenv("OAUTH_TOKEN_URL"),
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
        "grant_type": "client_credentials",
        "scope": "read write"
    },
    retry_on_auth_failure=True,
    refresh_token_threshold=300,
    base_headers={
        "User-Agent": f"{os.getenv('APP_NAME', 'WebFetch')}/{os.getenv('APP_VERSION', '1.0')}",
        "Accept": "application/json"
    }
)
```

## Database Configuration

### `DatabaseConfig` Options

The database configuration manages connection settings, pooling, and performance parameters.

#### Basic Configuration

```python
from web_fetch.models.extended_resources import DatabaseConfig, DatabaseType
from pydantic import SecretStr

# PostgreSQL configuration
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="myapp",
    username="user",
    password=SecretStr("password")
)
```

#### Configuration Options

| Option | Type | Default | Description | Effect |
|--------|------|---------|-------------|--------|
| `database_type` | `DatabaseType` | Required | Database type | Determines driver and connection method |
| `host` | `str` | Required | Database host | Connection endpoint |
| `port` | `int` | Required | Database port | Connection port |
| `database` | `str` | Required | Database name | Target database |
| `username` | `str` | Required | Database username | Authentication |
| `password` | `SecretStr` | Required | Database password | Authentication (secure) |
| `min_connections` | `int` | `1` | Minimum pool connections | Connection pool lower bound |
| `max_connections` | `int` | `10` | Maximum pool connections | Connection pool upper bound |
| `connection_timeout` | `float` | `30.0` | Connection timeout (seconds) | Connection establishment timeout |
| `query_timeout` | `float` | `60.0` | Query timeout (seconds) | Query execution timeout |
| `ssl_mode` | `Optional[str]` | `None` | SSL connection mode | Security settings |
| `extra_params` | `Dict[str, Any]` | `{}` | Additional parameters | Driver-specific options |

#### Database Types

##### 1. PostgreSQL Configuration

```python
pg_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="myapp",
    username="postgres",
    password=SecretStr("password"),
    min_connections=2,
    max_connections=20,
    connection_timeout=30.0,
    query_timeout=120.0,
    ssl_mode="prefer",  # "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    extra_params={
        "application_name": "web-fetch",
        "connect_timeout": 10,
        "command_timeout": 60,
        "server_settings": {
            "jit": "off",
            "timezone": "UTC"
        }
    }
)
```

**PostgreSQL SSL Modes:**

- `disable`: No SSL
- `allow`: SSL if available
- `prefer`: SSL preferred (default)
- `require`: SSL required
- `verify-ca`: SSL with CA verification
- `verify-full`: SSL with full verification

##### 2. MySQL Configuration

```python
mysql_config = DatabaseConfig(
    database_type=DatabaseType.MYSQL,
    host="localhost",
    port=3306,
    database="myapp",
    username="mysql_user",
    password=SecretStr("password"),
    min_connections=1,
    max_connections=15,
    connection_timeout=30.0,
    query_timeout=60.0,
    extra_params={
        "charset": "utf8mb4",
        "sql_mode": "STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO",
        "autocommit": True,
        "use_unicode": True,
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30
    }
)
```

##### 3. MongoDB Configuration

```python
mongo_config = DatabaseConfig(
    database_type=DatabaseType.MONGODB,
    host="localhost",
    port=27017,
    database="myapp",
    username="mongo_user",
    password=SecretStr("password"),
    min_connections=1,
    max_connections=10,
    connection_timeout=30.0,
    query_timeout=60.0,
    extra_params={
        "authSource": "admin",
        "authMechanism": "SCRAM-SHA-256",
        "ssl": True,
        "ssl_cert_reqs": "CERT_REQUIRED",
        "ssl_ca_certs": "/path/to/ca.pem",
        "replicaSet": "rs0",
        "readPreference": "secondaryPreferred",
        "w": "majority",
        "wtimeout": 5000,
        "journal": True
    }
)
```

#### Connection Pool Settings

```python
# High-throughput configuration
high_throughput_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="db.example.com",
    port=5432,
    database="production",
    username="app_user",
    password=SecretStr("secure_password"),
    min_connections=5,      # Keep connections warm
    max_connections=50,     # Handle high load
    connection_timeout=10.0, # Quick connection establishment
    query_timeout=30.0,     # Prevent long-running queries
    ssl_mode="require",
    extra_params={
        "application_name": "web-fetch-prod",
        "connect_timeout": 5,
        "command_timeout": 30
    }
)

# Development configuration
dev_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="dev",
    username="dev_user",
    password=SecretStr("dev_password"),
    min_connections=1,      # Minimal resources
    max_connections=5,      # Low concurrency
    connection_timeout=60.0, # Relaxed timeouts
    query_timeout=300.0,    # Allow long queries
    ssl_mode="disable",     # No SSL for local dev
    extra_params={
        "application_name": "web-fetch-dev"
    }
)
```

#### Performance Tuning

**Connection Pool Sizing:**

- **min_connections**: Set to expected baseline load
- **max_connections**: Set based on database limits and application needs
- **Rule of thumb**: max_connections = (CPU cores × 2) + effective_spindle_count

**Timeout Settings:**

- **connection_timeout**: 10-30 seconds for production
- **query_timeout**: Based on expected query complexity
- **Consider**: Network latency and query patterns

```python
# Performance-optimized configuration
perf_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="db-cluster.example.com",
    port=5432,
    database="analytics",
    username="analytics_user",
    password=SecretStr("analytics_password"),
    min_connections=10,     # Warm pool for immediate availability
    max_connections=100,    # High concurrency support
    connection_timeout=5.0,  # Fast connection establishment
    query_timeout=180.0,    # Allow complex analytics queries
    ssl_mode="require",
    extra_params={
        "application_name": "web-fetch-analytics",
        "connect_timeout": 3,
        "command_timeout": 180,
        "server_settings": {
            "work_mem": "256MB",
            "maintenance_work_mem": "1GB",
            "effective_cache_size": "8GB",
            "random_page_cost": "1.1"
        }
    }
)
```

## Cloud Storage Configuration

### `CloudStorageConfig` Options

The cloud storage configuration manages provider settings, authentication, and performance parameters.

#### Basic Configuration

```python
from web_fetch.models.extended_resources import CloudStorageConfig, CloudStorageProvider
from pydantic import SecretStr

# AWS S3 configuration
s3_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="my-bucket",
    access_key=SecretStr("AKIAIOSFODNN7EXAMPLE"),
    secret_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
    region="us-east-1"
)
```

#### Configuration Options

| Option | Type | Default | Description | Effect |
|--------|------|---------|-------------|--------|
| `provider` | `CloudStorageProvider` | Required | Storage provider | Determines SDK and API |
| `bucket_name` | `str` | Required | Bucket/container name | Target storage container |
| `access_key` | `Optional[SecretStr]` | `None` | Access key/account name | Authentication |
| `secret_key` | `Optional[SecretStr]` | `None` | Secret key/account key | Authentication |
| `token` | `Optional[SecretStr]` | `None` | Session token | Temporary credentials |
| `region` | `Optional[str]` | `None` | Storage region | Geographic location |
| `endpoint_url` | `Optional[str]` | `None` | Custom endpoint | Alternative endpoints |
| `multipart_threshold` | `int` | `8MB` | Multipart upload threshold | Upload optimization |
| `max_concurrency` | `int` | `10` | Maximum concurrent operations | Performance tuning |
| `retry_attempts` | `int` | `3` | Number of retry attempts | Reliability |
| `extra_config` | `Dict[str, Any]` | `{}` | Provider-specific options | Advanced settings |

#### Provider Configurations

##### 1. AWS S3 Configuration

```python
s3_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="my-s3-bucket",
    access_key=SecretStr("AKIAIOSFODNN7EXAMPLE"),
    secret_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
    token=SecretStr("session-token"),  # Optional for temporary credentials
    region="us-east-1",
    endpoint_url="https://s3.amazonaws.com",  # Optional custom endpoint
    multipart_threshold=16 * 1024 * 1024,  # 16MB threshold
    max_concurrency=20,
    retry_attempts=5,
    extra_config={
        "signature_version": "s3v4",
        "addressing_style": "virtual",
        "use_ssl": True,
        "verify": True,  # SSL certificate verification
        "config": {
            "retries": {
                "max_attempts": 5,
                "mode": "adaptive"
            },
            "max_pool_connections": 50
        }
    }
)
```

**AWS S3 Authentication Options:**

1. **Access Key + Secret Key** (long-term credentials)
2. **Access Key + Secret Key + Session Token** (temporary credentials)
3. **IAM Role** (when running on EC2/ECS)
4. **Environment Variables** (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

##### 2. Google Cloud Storage Configuration

```python
gcs_config = CloudStorageConfig(
    provider=CloudStorageProvider.GOOGLE_CLOUD,
    bucket_name="my-gcs-bucket",
    region="us-central1",
    multipart_threshold=32 * 1024 * 1024,  # 32MB threshold
    max_concurrency=15,
    retry_attempts=3,
    extra_config={
        "credentials_path": "/path/to/service-account.json",
        "project_id": "my-gcp-project",
        "default_timeout": 60,
        "default_retry": {
            "deadline": 120,
            "maximum": 5,
            "multiplier": 2.0,
            "predicate": "default"
        },
        "client_options": {
            "api_endpoint": "https://storage.googleapis.com"
        }
    }
)
```

**Google Cloud Storage Authentication Options:**

1. **Service Account Key File** (JSON credentials)
2. **Application Default Credentials** (when running on GCP)
3. **Environment Variable** (GOOGLE_APPLICATION_CREDENTIALS)
4. **OAuth 2.0** (for user authentication)

##### 3. Azure Blob Storage Configuration

```python
azure_config = CloudStorageConfig(
    provider=CloudStorageProvider.AZURE_BLOB,
    bucket_name="my-container",
    access_key=SecretStr("mystorageaccount"),  # Storage account name
    secret_key=SecretStr("storage-account-key"),  # Storage account key
    region="eastus",
    multipart_threshold=64 * 1024 * 1024,  # 64MB threshold
    max_concurrency=10,
    retry_attempts=4,
    extra_config={
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=key;EndpointSuffix=core.windows.net",
        "max_single_put_size": 64 * 1024 * 1024,
        "max_block_size": 4 * 1024 * 1024,
        "retry_policy": {
            "retry_total": 4,
            "retry_connect": 4,
            "retry_read": 4,
            "retry_status": 4,
            "backoff_factor": 0.8
        },
        "socket_timeout": 20
    }
)
```

**Azure Blob Storage Authentication Options:**

1. **Account Name + Account Key**
2. **Connection String**
3. **Shared Access Signature (SAS)**
4. **Azure Active Directory** (OAuth 2.0)

#### Performance Optimization

```python
# High-performance configuration
high_perf_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="high-throughput-bucket",
    access_key=SecretStr("access-key"),
    secret_key=SecretStr("secret-key"),
    region="us-east-1",
    multipart_threshold=8 * 1024 * 1024,   # 8MB - smaller for faster uploads
    max_concurrency=50,                     # High concurrency
    retry_attempts=3,                       # Balanced retry attempts
    extra_config={
        "config": {
            "max_pool_connections": 100,    # Large connection pool
            "retries": {
                "max_attempts": 3,
                "mode": "adaptive"
            }
        },
        "transfer_config": {
            "multipart_threshold": 8 * 1024 * 1024,
            "max_concurrency": 50,
            "multipart_chunksize": 8 * 1024 * 1024,
            "use_threads": True
        }
    }
)

# Cost-optimized configuration
cost_optimized_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="cost-optimized-bucket",
    access_key=SecretStr("access-key"),
    secret_key=SecretStr("secret-key"),
    region="us-east-1",
    multipart_threshold=64 * 1024 * 1024,  # 64MB - larger chunks
    max_concurrency=5,                      # Lower concurrency
    retry_attempts=2,                       # Fewer retries
    extra_config={
        "config": {
            "max_pool_connections": 10,     # Smaller connection pool
            "retries": {
                "max_attempts": 2,
                "mode": "standard"
            }
        },
        "storage_class": "STANDARD_IA",     # Infrequent Access storage class
        "server_side_encryption": "AES256"
    }
)
```

#### Security Best Practices

```python
# Security-focused configuration
secure_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name="secure-bucket",
    access_key=SecretStr(os.getenv("AWS_ACCESS_KEY_ID")),
    secret_key=SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY")),
    token=SecretStr(os.getenv("AWS_SESSION_TOKEN")),  # If using temporary credentials
    region="us-east-1",
    multipart_threshold=16 * 1024 * 1024,
    max_concurrency=10,
    retry_attempts=3,
    extra_config={
        "use_ssl": True,                    # Always use HTTPS
        "verify": True,                     # Verify SSL certificates
        "signature_version": "s3v4",        # Use latest signature version
        "config": {
            "retries": {
                "max_attempts": 3,
                "mode": "adaptive"
            }
        },
        "server_side_encryption": "aws:kms",
        "sse_kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        "bucket_key_enabled": True
    }
)
```
