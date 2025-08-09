# Troubleshooting Guide - Extended Resource Types

This guide provides troubleshooting information and performance optimization recommendations for all extended resource types.

## Table of Contents

- [Common Issues](#common-issues)
- [RSS/Atom Feed Troubleshooting](#rssatom-feed-troubleshooting)
- [Authenticated API Troubleshooting](#authenticated-api-troubleshooting)
- [Database Troubleshooting](#database-troubleshooting)
- [Cloud Storage Troubleshooting](#cloud-storage-troubleshooting)
- [Performance Optimization](#performance-optimization)
- [Monitoring and Debugging](#monitoring-and-debugging)

## Common Issues

### Import Errors

**Problem**: Missing dependencies for extended resource types

```python
ImportError: No module named 'asyncpg'
ImportError: No module named 'boto3'
ImportError: No module named 'motor'
```

**Solution**: Install required dependencies

```bash
# Install all extended dependencies
pip install asyncpg aiomysql motor boto3 google-cloud-storage azure-storage-blob

# Or install web-fetch with extended dependencies
pip install web-fetch[extended]
```

### Configuration Validation Errors

**Problem**: Pydantic validation errors during configuration

```python
ValidationError: 1 validation error for DatabaseConfig
password
  field required (type=value_error.missing)
```

**Solution**: Ensure all required fields are provided with correct types

```python
from pydantic import SecretStr

# Correct configuration
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="myapp",
    username="user",
    password=SecretStr("password")  # Use SecretStr for passwords
)
```

### Async Context Issues

**Problem**: RuntimeError when using components outside async context

```python
RuntimeError: no running event loop
```

**Solution**: Ensure components are used within async functions

```python
import asyncio

async def main():
    component = RSSComponent()
    result = await component.fetch(request)
    return result

# Run with asyncio
result = asyncio.run(main())
```

## RSS/Atom Feed Troubleshooting

### Feed Parsing Issues

#### Problem: Invalid XML/Feed Format

**Symptoms:**

- `RSS feed fetch error: Invalid XML content`
- Empty or malformed feed data

**Diagnosis:**

```python
# Check raw feed content
result = await fetch_rss_feed("https://example.com/feed.xml")
if not result.is_success:
    print(f"Error: {result.error}")
    print(f"Status code: {result.status_code}")
```

**Solutions:**

1. **Verify feed URL**: Ensure the URL returns valid RSS/Atom content
2. **Check feed format**: Some feeds may use non-standard formats
3. **Handle redirects**: Enable redirect following in configuration

```python
rss_config = RSSConfig(
    follow_redirects=True,
    validate_dates=False,  # Skip date validation for malformed feeds
    user_agent="YourApp/1.0"  # Some feeds require User-Agent
)
```

#### Problem: Feed Access Denied

**Symptoms:**

- HTTP 403 Forbidden errors
- HTTP 429 Too Many Requests

**Solutions:**

1. **Add User-Agent header**:

```python
rss_config = RSSConfig(
    user_agent="YourApp/1.0 (+https://yoursite.com/contact)"
)
```

2. **Implement rate limiting**:

```python
import asyncio

async def fetch_feeds_with_delay(feed_urls, delay=1.0):
    results = []
    for url in feed_urls:
        result = await fetch_rss_feed(url)
        results.append(result)
        await asyncio.sleep(delay)  # Rate limiting
    return results
```

3. **Use caching to reduce requests**:

```python
config = ResourceConfig(
    enable_cache=True,
    cache_ttl_seconds=3600  # Cache for 1 hour
)
```

#### Problem: Memory Issues with Large Feeds

**Symptoms:**

- High memory usage
- Slow parsing performance

**Solutions:**

1. **Limit feed items**:

```python
rss_config = RSSConfig(
    max_items=50,  # Limit to 50 items
    include_content=False  # Skip full content
)
```

2. **Stream processing for large feeds**:

```python
async def process_feed_incrementally(feed_url, batch_size=10):
    rss_config = RSSConfig(max_items=batch_size)
    
    offset = 0
    while True:
        # Process in batches
        result = await fetch_rss_feed(feed_url, config=rss_config)
        if not result.is_success or not result.content['items']:
            break
            
        # Process batch
        for item in result.content['items']:
            yield item
            
        offset += batch_size
```

### Performance Optimization for RSS

1. **Optimize parsing configuration**:

```python
# High-performance configuration
rss_config = RSSConfig(
    max_items=25,           # Limit items
    include_content=False,  # Skip content parsing
    validate_dates=False,   # Skip date validation
    follow_redirects=False  # Direct access only
)
```

2. **Use connection pooling**:

```python
from web_fetch.models.http import FetchConfig

http_config = FetchConfig(
    max_connections=20,
    max_connections_per_host=5,
    connection_timeout=10.0
)

component = RSSComponent(http_config=http_config)
```

3. **Implement concurrent fetching**:

```python
import asyncio

async def fetch_multiple_feeds(feed_urls, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_single(url):
        async with semaphore:
            return await fetch_rss_feed(url)
    
    tasks = [fetch_single(url) for url in feed_urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## Authenticated API Troubleshooting

### Authentication Issues

#### Problem: Token Expired or Invalid

**Symptoms:**

- HTTP 401 Unauthorized
- HTTP 403 Forbidden
- `Authentication failed: Invalid credentials`

**Diagnosis:**

```python
result = await fetch_authenticated_api(api_url, auth_method, auth_config)
if not result.is_success:
    auth_metadata = result.metadata.get('authentication', {})
    print(f"Auth method: {auth_metadata.get('method')}")
    print(f"Authenticated: {auth_metadata.get('authenticated')}")
    print(f"Error: {auth_metadata.get('error')}")
```

**Solutions:**

1. **Enable automatic retry**:

```python
api_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={...},
    retry_on_auth_failure=True,
    refresh_token_threshold=600  # Refresh 10 minutes early
)
```

2. **Check token expiration**:

```python
import jwt
import time

def check_jwt_expiration(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded.get('exp')
        if exp and exp < time.time():
            print("Token expired")
            return False
        return True
    except Exception as e:
        print(f"Token validation error: {e}")
        return False
```

3. **Implement token refresh logic**:

```python
class TokenManager:
    def __init__(self, oauth_config):
        self.oauth_config = oauth_config
        self.token = None
        self.expires_at = None
    
    async def get_valid_token(self):
        if not self.token or time.time() >= (self.expires_at - 300):
            await self.refresh_token()
        return self.token
    
    async def refresh_token(self):
        # Implement OAuth token refresh
        pass
```

#### Problem: OAuth 2.0 Configuration Issues

**Common OAuth Errors:**

- `invalid_client`: Client ID/secret incorrect
- `invalid_grant`: Grant type not supported
- `invalid_scope`: Requested scope not available

**Solutions:**

1. **Verify OAuth configuration**:

```python
oauth_config = {
    "token_url": "https://api.example.com/oauth/token",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "grant_type": "client_credentials",  # Verify supported grant types
    "scope": "read write"  # Verify available scopes
}
```

2. **Test OAuth flow manually**:

```bash
curl -X POST https://api.example.com/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=your-client-id&client_secret=your-client-secret&scope=read"
```

### API Rate Limiting

#### Problem: Rate Limit Exceeded

**Symptoms:**

- HTTP 429 Too Many Requests
- `X-RateLimit-Remaining: 0` headers

**Solutions:**

1. **Implement exponential backoff**:

```python
import asyncio
import random

async def api_request_with_backoff(url, auth_config, max_retries=5):
    for attempt in range(max_retries):
        result = await fetch_authenticated_api(url, "api_key", auth_config)
        
        if result.status_code != 429:
            return result
        
        # Exponential backoff with jitter
        delay = (2 ** attempt) + random.uniform(0, 1)
        await asyncio.sleep(delay)
    
    return result
```

2. **Monitor rate limit headers**:

```python
def check_rate_limits(result):
    headers = result.headers
    remaining = headers.get('X-RateLimit-Remaining')
    reset_time = headers.get('X-RateLimit-Reset')
    
    if remaining and int(remaining) < 10:
        print(f"Rate limit warning: {remaining} requests remaining")
        if reset_time:
            print(f"Resets at: {reset_time}")
```

3. **Implement request queuing**:

```python
import asyncio
from collections import deque

class RateLimitedAPIClient:
    def __init__(self, requests_per_second=10):
        self.requests_per_second = requests_per_second
        self.request_queue = deque()
        self.last_request_time = 0
    
    async def make_request(self, url, auth_config):
        # Calculate delay to maintain rate limit
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
        return await fetch_authenticated_api(url, "api_key", auth_config)
```

### Performance Optimization for APIs

1. **Connection reuse**:

```python
api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={...},
    base_headers={
        "Connection": "keep-alive",
        "User-Agent": "YourApp/1.0"
    }
)
```

2. **Batch API requests**:

```python
async def batch_api_requests(endpoints, auth_config, batch_size=10):
    results = []
    for i in range(0, len(endpoints), batch_size):
        batch = endpoints[i:i + batch_size]
        batch_tasks = [
            fetch_authenticated_api(endpoint, "api_key", auth_config)
            for endpoint in batch
        ]
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
    return results
```

3. **Response compression**:

```python
api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={...},
    base_headers={
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json"
    }
)
```

## Database Troubleshooting

### Connection Issues

#### Problem: Database Connection Failed

**Symptoms:**

- `Database query error: Connection failed`
- `asyncpg.exceptions.ConnectionDoesNotExistError`
- `aiomysql.Error: Can't connect to MySQL server`

**Diagnosis:**

```python
# Test database connectivity
async def test_db_connection(db_config):
    try:
        component = DatabaseComponent(db_config=db_config)
        # Simple connectivity test
        test_query = DatabaseQuery(query="SELECT 1", fetch_mode="one")
        request = ResourceRequest(
            uri=AnyUrl(f"{db_config.database_type.value}://{db_config.host}:{db_config.port}"),
            kind=ResourceKind.DATABASE,
            options={"query": test_query.dict()}
        )
        result = await component.fetch(request)
        return result.is_success
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False
```

**Solutions:**

1. **Verify connection parameters**:

```python
# Check each parameter
print(f"Host: {db_config.host}")
print(f"Port: {db_config.port}")
print(f"Database: {db_config.database}")
print(f"Username: {db_config.username}")
# Don't print password in logs!
```

2. **Test network connectivity**:

```bash
# Test port connectivity
telnet db-host 5432

# Test DNS resolution
nslookup db-host

# Test with database client
psql -h db-host -p 5432 -U username -d database
```

3. **Adjust connection timeouts**:

```python
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="remote-db.example.com",
    port=5432,
    database="myapp",
    username="user",
    password=SecretStr("password"),
    connection_timeout=60.0,  # Increase timeout for slow networks
    query_timeout=120.0
)
```

#### Problem: SSL/TLS Connection Issues

**Symptoms:**

- `SSL connection has been closed unexpectedly`
- `certificate verify failed`

**Solutions:**

1. **Configure SSL mode**:

```python
# PostgreSQL SSL configuration
pg_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="secure-db.example.com",
    port=5432,
    database="myapp",
    username="user",
    password=SecretStr("password"),
    ssl_mode="require",  # or "verify-full" for strict verification
    extra_params={
        "sslcert": "/path/to/client-cert.pem",
        "sslkey": "/path/to/client-key.pem",
        "sslrootcert": "/path/to/ca-cert.pem"
    }
)
```

2. **Disable SSL for development**:

```python
dev_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="dev",
    username="dev_user",
    password=SecretStr("dev_password"),
    ssl_mode="disable"  # Only for local development
)
```

### Query Performance Issues

#### Problem: Slow Query Execution

**Symptoms:**

- High query execution times
- Database timeouts
- Connection pool exhaustion

**Diagnosis:**

```python
import time

async def diagnose_query_performance(component, request):
    start_time = time.time()
    result = await component.fetch(request)
    execution_time = time.time() - start_time

    print(f"Query execution time: {execution_time:.2f}s")
    print(f"Row count: {result.content.get('row_count', 0) if result.is_success else 'N/A'}")

    if execution_time > 5.0:
        print("WARNING: Slow query detected")

    return result
```

**Solutions:**

1. **Optimize queries**:

```python
# Use LIMIT for large result sets
query = DatabaseQuery(
    query="SELECT * FROM large_table WHERE condition = $1 LIMIT 1000",
    parameters={"$1": "value"},
    fetch_mode="all",
    limit=1000
)

# Use indexes
query = DatabaseQuery(
    query="SELECT * FROM users WHERE email = $1",  # Ensure email is indexed
    parameters={"$1": "user@example.com"},
    fetch_mode="one"
)
```

2. **Adjust connection pool settings**:

```python
# High-performance configuration
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="db.example.com",
    port=5432,
    database="production",
    username="app_user",
    password=SecretStr("password"),
    min_connections=10,     # Keep connections warm
    max_connections=50,     # Handle high concurrency
    connection_timeout=10.0,
    query_timeout=30.0,     # Prevent long-running queries
    extra_params={
        "command_timeout": 30,
        "server_settings": {
            "work_mem": "256MB",
            "effective_cache_size": "8GB"
        }
    }
)
```
