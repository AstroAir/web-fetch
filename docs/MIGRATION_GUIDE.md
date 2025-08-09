# Migration Guide - Extended Resource Types

This guide helps users migrate from basic HTTP-only usage to the extended resource types and provides advanced integration patterns.

## Table of Contents

- [Migration Overview](#migration-overview)
- [From Basic HTTP to Extended Resources](#from-basic-http-to-extended-resources)
- [Component Migration Patterns](#component-migration-patterns)
- [Advanced Integration Examples](#advanced-integration-examples)
- [Performance Considerations](#performance-considerations)
- [Breaking Changes](#breaking-changes)

## Migration Overview

### What's New

The extended resource types add powerful new capabilities:

- **RSS/Atom Feed Processing**: Structured feed parsing with validation
- **Authenticated API Access**: Integrated authentication with multiple methods
- **Database Connectivity**: Direct database access with connection pooling
- **Cloud Storage Operations**: Unified cloud storage interface

### Backward Compatibility

All existing HTTP functionality remains unchanged. Extended resource types are additive and don't affect existing code.

```python
# Existing code continues to work unchanged
from web_fetch import fetch_url

result = await fetch_url("https://api.example.com/data")
# This still works exactly as before
```

## From Basic HTTP to Extended Resources

### Basic HTTP to RSS Feeds

**Before (Basic HTTP):**

```python
import asyncio
import xml.etree.ElementTree as ET
from web_fetch import fetch_url

async def fetch_rss_old_way():
    # Manual RSS parsing
    result = await fetch_url("https://example.com/feed.xml")
    if result.is_success:
        try:
            root = ET.fromstring(result.content)
            items = []
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                items.append({"title": title, "link": link})
            return items
        except ET.ParseError as e:
            print(f"XML parsing error: {e}")
            return []
    return []
```

**After (Extended Resources):**

```python
from web_fetch import fetch_rss_feed
from web_fetch.models.extended_resources import RSSConfig

async def fetch_rss_new_way():
    # Automatic RSS parsing with validation
    config = RSSConfig(
        max_items=50,
        include_content=True,
        validate_dates=True
    )
    
    result = await fetch_rss_feed("https://example.com/feed.xml", config=config)
    if result.is_success:
        return result.content['items']
    return []
```

**Benefits of Migration:**

- Automatic format detection (RSS/Atom)
- Built-in validation and error handling
- Structured metadata extraction
- Caching support
- Better performance

### Basic HTTP to Authenticated APIs

**Before (Manual Authentication):**

```python
import base64
import json
from web_fetch import fetch_url

async def fetch_api_old_way():
    # Manual OAuth token management
    token_response = await fetch_url(
        "https://api.example.com/oauth/token",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data="grant_type=client_credentials&client_id=id&client_secret=secret"
    )
    
    if not token_response.is_success:
        return None
    
    token_data = json.loads(token_response.content)
    access_token = token_data.get('access_token')
    
    # Use token for API request
    api_response = await fetch_url(
        "https://api.example.com/data",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    return api_response
```

**After (Integrated Authentication):**

```python
from web_fetch import fetch_authenticated_api
from web_fetch.models.extended_resources import AuthenticatedAPIConfig

async def fetch_api_new_way():
    # Automatic authentication management
    config = AuthenticatedAPIConfig(
        auth_method="oauth2",
        auth_config={
            "token_url": "https://api.example.com/oauth/token",
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "grant_type": "client_credentials"
        },
        retry_on_auth_failure=True,
        refresh_token_threshold=300
    )
    
    result = await fetch_authenticated_api(
        "https://api.example.com/data",
        config=config
    )
    
    return result
```

**Benefits of Migration:**

- Automatic token management and refresh
- Multiple authentication methods supported
- Built-in retry logic for auth failures
- Secure credential handling
- Comprehensive error handling

### Basic HTTP to Database Access

**Before (External Database Library):**

```python
import asyncpg
import json

async def query_database_old_way():
    # Manual connection management
    conn = None
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="user",
            password="password",
            database="myapp"
        )
        
        rows = await conn.fetch("SELECT * FROM users WHERE active = $1", True)
        return [dict(row) for row in rows]
    
    except Exception as e:
        print(f"Database error: {e}")
        return []
    finally:
        if conn:
            await conn.close()
```

**After (Integrated Database Component):**

```python
from web_fetch import fetch_database_query
from web_fetch.models.extended_resources import DatabaseConfig, DatabaseQuery, DatabaseType
from pydantic import SecretStr

async def query_database_new_way():
    # Automatic connection pooling and management
    db_config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="myapp",
        username="user",
        password=SecretStr("password"),
        min_connections=2,
        max_connections=10
    )
    
    query = DatabaseQuery(
        query="SELECT * FROM users WHERE active = $1",
        parameters={"$1": True},
        fetch_mode="all"
    )
    
    result = await fetch_database_query(db_config, query)
    if result.is_success:
        return result.content['data']
    return []
```

**Benefits of Migration:**

- Automatic connection pooling
- Multiple database support (PostgreSQL, MySQL, MongoDB)
- Built-in error handling and retries
- Secure credential management
- Performance optimization

## Component Migration Patterns

### Gradual Migration Strategy

Migrate components incrementally to minimize risk:

```python
# Phase 1: Keep existing HTTP calls, add new RSS functionality
class DataFetcher:
    def __init__(self):
        self.use_extended_resources = False
    
    async def fetch_api_data(self, url):
        if self.use_extended_resources:
            return await self._fetch_with_auth(url)
        else:
            return await self._fetch_basic_http(url)
    
    async def _fetch_basic_http(self, url):
        # Existing HTTP implementation
        from web_fetch import fetch_url
        return await fetch_url(url)
    
    async def _fetch_with_auth(self, url):
        # New authenticated API implementation
        from web_fetch import fetch_authenticated_api
        config = self._get_auth_config()
        return await fetch_authenticated_api(url, config=config)
    
    def enable_extended_resources(self):
        """Enable extended resources after testing."""
        self.use_extended_resources = True

# Phase 2: Gradually enable extended resources
fetcher = DataFetcher()
# Test with basic HTTP first
result = await fetcher.fetch_api_data("https://api.example.com/data")

# Enable extended resources after validation
fetcher.enable_extended_resources()
result = await fetcher.fetch_api_data("https://api.example.com/data")
```

### Configuration Migration

Migrate configuration gradually:

```python
# Old configuration
OLD_CONFIG = {
    "api_url": "https://api.example.com",
    "api_key": "your-api-key",
    "timeout": 30,
    "retries": 3
}

# New configuration with backward compatibility
class MigrationConfig:
    def __init__(self, old_config=None):
        if old_config:
            self.api_config = self._migrate_api_config(old_config)
            self.http_config = self._migrate_http_config(old_config)
        else:
            self.api_config = None
            self.http_config = None
    
    def _migrate_api_config(self, old_config):
        from web_fetch.models.extended_resources import AuthenticatedAPIConfig
        
        return AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": old_config.get("api_key"),
                "key_name": "X-API-Key",
                "location": "header"
            },
            retry_on_auth_failure=True
        )
    
    def _migrate_http_config(self, old_config):
        from web_fetch.models.http import FetchConfig
        
        return FetchConfig(
            timeout_seconds=old_config.get("timeout", 30),
            max_retries=old_config.get("retries", 3),
            verify_ssl=True
        )

# Usage
config = MigrationConfig(OLD_CONFIG)
```

## Advanced Integration Examples

### Multi-Source Data Aggregation

Combine multiple resource types for comprehensive data collection:

```python
import asyncio
from typing import List, Dict, Any
from web_fetch import (
    fetch_rss_feed, fetch_authenticated_api, 
    fetch_database_query, fetch_cloud_storage
)

class DataAggregator:
    def __init__(self):
        self.rss_config = self._setup_rss_config()
        self.api_config = self._setup_api_config()
        self.db_config = self._setup_db_config()
        self.storage_config = self._setup_storage_config()
    
    async def aggregate_user_data(self, user_id: str) -> Dict[str, Any]:
        """Aggregate user data from multiple sources."""
        
        # Fetch data from multiple sources concurrently
        tasks = [
            self._fetch_user_feeds(user_id),
            self._fetch_user_api_data(user_id),
            self._fetch_user_db_data(user_id),
            self._fetch_user_files(user_id)
        ]
        
        feeds, api_data, db_data, files = await asyncio.gather(
            *tasks, return_exceptions=True
        )
        
        # Combine results
        return {
            "user_id": user_id,
            "feeds": feeds if not isinstance(feeds, Exception) else [],
            "api_data": api_data if not isinstance(api_data, Exception) else {},
            "profile": db_data if not isinstance(db_data, Exception) else {},
            "files": files if not isinstance(files, Exception) else [],
            "aggregated_at": datetime.utcnow().isoformat()
        }
    
    async def _fetch_user_feeds(self, user_id: str) -> List[Dict]:
        """Fetch user's RSS feeds."""
        user_feeds = await self._get_user_feed_urls(user_id)
        
        feed_tasks = [
            fetch_rss_feed(feed_url, config=self.rss_config)
            for feed_url in user_feeds
        ]
        
        results = await asyncio.gather(*feed_tasks, return_exceptions=True)
        
        feeds = []
        for result in results:
            if not isinstance(result, Exception) and result.is_success:
                feeds.extend(result.content['items'])
        
        return feeds
    
    async def _fetch_user_api_data(self, user_id: str) -> Dict:
        """Fetch user data from external API."""
        result = await fetch_authenticated_api(
            f"https://api.example.com/users/{user_id}",
            config=self.api_config
        )
        
        if result.is_success:
            return result.content
        return {}
    
    async def _fetch_user_db_data(self, user_id: str) -> Dict:
        """Fetch user profile from database."""
        from web_fetch.models.extended_resources import DatabaseQuery
        
        query = DatabaseQuery(
            query="SELECT * FROM user_profiles WHERE user_id = $1",
            parameters={"$1": user_id},
            fetch_mode="one"
        )
        
        result = await fetch_database_query(self.db_config, query)
        
        if result.is_success and result.content['data']:
            return result.content['data'][0]
        return {}
    
    async def _fetch_user_files(self, user_id: str) -> List[Dict]:
        """Fetch user files from cloud storage."""
        from web_fetch.models.extended_resources import CloudStorageOperation
        
        operation = CloudStorageOperation(
            operation="list",
            prefix=f"users/{user_id}/"
        )
        
        result = await fetch_cloud_storage(self.storage_config, operation)
        
        if result.is_success:
            return result.content.get('objects', [])
        return []

# Usage
aggregator = DataAggregator()
user_data = await aggregator.aggregate_user_data("user123")
```

### Event-Driven Processing Pipeline

Create a processing pipeline that reacts to different data sources:

```python
import asyncio
from typing import AsyncGenerator
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    RSS_UPDATE = "rss_update"
    API_DATA = "api_data"
    DB_CHANGE = "db_change"
    FILE_UPLOAD = "file_upload"

@dataclass
class DataEvent:
    event_type: EventType
    source: str
    data: Dict[str, Any]
    timestamp: datetime

class EventDrivenProcessor:
    def __init__(self):
        self.event_queue = asyncio.Queue()
        self.processors = {
            EventType.RSS_UPDATE: self._process_rss_event,
            EventType.API_DATA: self._process_api_event,
            EventType.DB_CHANGE: self._process_db_event,
            EventType.FILE_UPLOAD: self._process_file_event
        }
    
    async def start_monitoring(self):
        """Start monitoring all data sources."""
        tasks = [
            self._monitor_rss_feeds(),
            self._monitor_api_endpoints(),
            self._monitor_database_changes(),
            self._monitor_file_uploads(),
            self._process_events()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_rss_feeds(self):
        """Monitor RSS feeds for updates."""
        feed_urls = ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
        
        while True:
            for feed_url in feed_urls:
                try:
                    result = await fetch_rss_feed(feed_url)
                    if result.is_success:
                        event = DataEvent(
                            event_type=EventType.RSS_UPDATE,
                            source=feed_url,
                            data=result.content,
                            timestamp=datetime.utcnow()
                        )
                        await self.event_queue.put(event)
                except Exception as e:
                    print(f"RSS monitoring error: {e}")
            
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def _process_events(self):
        """Process events from the queue."""
        while True:
            event = await self.event_queue.get()
            
            processor = self.processors.get(event.event_type)
            if processor:
                try:
                    await processor(event)
                except Exception as e:
                    print(f"Event processing error: {e}")
            
            self.event_queue.task_done()
    
    async def _process_rss_event(self, event: DataEvent):
        """Process RSS update events."""
        print(f"Processing RSS update from {event.source}")
        
        # Extract and process new items
        items = event.data.get('items', [])
        for item in items:
            # Process each RSS item
            await self._store_rss_item(item)
    
    async def _store_rss_item(self, item: Dict):
        """Store RSS item in database."""
        from web_fetch.models.extended_resources import DatabaseQuery
        
        query = DatabaseQuery(
            query="INSERT INTO rss_items (title, link, description, pub_date) VALUES ($1, $2, $3, $4)",
            parameters={
                "$1": item.get('title'),
                "$2": item.get('link'),
                "$3": item.get('description'),
                "$4": item.get('pub_date')
            },
            fetch_mode="none"
        )
        
        await fetch_database_query(self.db_config, query)

# Usage
processor = EventDrivenProcessor()
await processor.start_monitoring()
```

### Microservices Integration Pattern

Integrate extended resources in a microservices architecture:

```python
from fastapi import FastAPI, BackgroundTasks
from typing import Optional
import asyncio

app = FastAPI()

class MicroserviceIntegrator:
    def __init__(self):
        self.services = {
            "feed_service": FeedService(),
            "auth_service": AuthService(),
            "data_service": DataService(),
            "storage_service": StorageService()
        }

    async def process_request(self, request_type: str, **kwargs):
        """Route requests to appropriate services."""
        service_map = {
            "feed": self.services["feed_service"],
            "api": self.services["auth_service"],
            "database": self.services["data_service"],
            "storage": self.services["storage_service"]
        }

        service = service_map.get(request_type)
        if service:
            return await service.process(**kwargs)

        raise ValueError(f"Unknown request type: {request_type}")

class FeedService:
    async def process(self, feed_url: str, **kwargs):
        """Process RSS feed requests."""
        result = await fetch_rss_feed(feed_url)

        # Post-process and enrich data
        if result.is_success:
            enriched_data = await self._enrich_feed_data(result.content)
            return {"status": "success", "data": enriched_data}

        return {"status": "error", "error": result.error}

    async def _enrich_feed_data(self, feed_data):
        """Enrich feed data with additional metadata."""
        # Add sentiment analysis, categorization, etc.
        return feed_data

# FastAPI endpoints
integrator = MicroserviceIntegrator()

@app.post("/api/v1/feeds/process")
async def process_feed(feed_url: str, background_tasks: BackgroundTasks):
    """Process RSS feed asynchronously."""

    # Process immediately for small feeds
    result = await integrator.process_request("feed", feed_url=feed_url)

    # Queue background processing for large feeds
    background_tasks.add_task(
        process_feed_background,
        feed_url=feed_url
    )

    return result

async def process_feed_background(feed_url: str):
    """Background processing for large feeds."""
    # Implement heavy processing logic
    pass
```

## Performance Considerations

### Connection Pooling and Resource Management

Optimize performance with proper resource management:

```python
class OptimizedResourceManager:
    def __init__(self):
        self.connection_pools = {}
        self.cache = {}
        self.metrics = PerformanceMetrics()

    async def get_database_pool(self, db_config):
        """Get or create database connection pool."""
        pool_key = f"{db_config.host}:{db_config.port}:{db_config.database}"

        if pool_key not in self.connection_pools:
            self.connection_pools[pool_key] = await self._create_db_pool(db_config)

        return self.connection_pools[pool_key]

    async def _create_db_pool(self, db_config):
        """Create optimized database connection pool."""
        if db_config.database_type == DatabaseType.POSTGRESQL:
            import asyncpg
            return await asyncpg.create_pool(
                host=db_config.host,
                port=db_config.port,
                user=db_config.username,
                password=db_config.password.get_secret_value(),
                database=db_config.database,
                min_size=db_config.min_connections,
                max_size=db_config.max_connections,
                command_timeout=db_config.query_timeout
            )

    async def execute_with_caching(self, operation, cache_key, ttl=300):
        """Execute operation with intelligent caching."""

        # Check cache first
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if time.time() - cache_entry['timestamp'] < ttl:
                self.metrics.record_cache_hit()
                return cache_entry['data']

        # Execute operation
        start_time = time.time()
        result = await operation()
        execution_time = time.time() - start_time

        # Cache successful results
        if result.is_success:
            self.cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }

        self.metrics.record_operation(execution_time)
        return result

class PerformanceMetrics:
    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.operation_times = []

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_cache_miss(self):
        self.cache_misses += 1

    def record_operation(self, execution_time):
        self.operation_times.append(execution_time)

        # Keep only recent metrics
        if len(self.operation_times) > 1000:
            self.operation_times = self.operation_times[-1000:]

    def get_stats(self):
        total_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0

        avg_time = sum(self.operation_times) / len(self.operation_times) if self.operation_times else 0

        return {
            "cache_hit_rate": cache_hit_rate,
            "average_operation_time": avg_time,
            "total_operations": len(self.operation_times)
        }
```

### Batch Processing Optimization

Optimize batch operations for better performance:

```python
class BatchProcessor:
    def __init__(self, batch_size=100, max_concurrent=10):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_feeds_batch(self, feed_urls: List[str]):
        """Process multiple RSS feeds efficiently."""

        # Split into batches
        batches = [
            feed_urls[i:i + self.batch_size]
            for i in range(0, len(feed_urls), self.batch_size)
        ]

        # Process batches concurrently
        tasks = [
            self._process_feed_batch(batch)
            for batch in batches
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_results = []
        for batch_result in results:
            if not isinstance(batch_result, Exception):
                all_results.extend(batch_result)

        return all_results

    async def _process_feed_batch(self, feed_urls: List[str]):
        """Process a single batch of feeds."""
        async with self.semaphore:
            tasks = [
                fetch_rss_feed(url)
                for url in feed_urls
            ]

            return await asyncio.gather(*tasks, return_exceptions=True)

    async def process_database_batch(self, queries: List[DatabaseQuery], db_config):
        """Process multiple database queries efficiently."""

        # Group queries by type for optimization
        read_queries = [q for q in queries if q.query.upper().startswith('SELECT')]
        write_queries = [q for q in queries if not q.query.upper().startswith('SELECT')]

        # Process reads concurrently, writes sequentially
        read_tasks = [
            fetch_database_query(db_config, query)
            for query in read_queries
        ]

        read_results = await asyncio.gather(*read_tasks, return_exceptions=True)

        write_results = []
        for query in write_queries:
            result = await fetch_database_query(db_config, query)
            write_results.append(result)

        return read_results + write_results
```

## Breaking Changes

### Version Compatibility

The extended resource types maintain backward compatibility, but some advanced features may require updates:

#### Configuration Changes

```python
# Old style (still works)
from web_fetch import fetch_url

result = await fetch_url("https://api.example.com", headers={"Authorization": "Bearer token"})

# New style (recommended for new code)
from web_fetch import fetch_authenticated_api
from web_fetch.models.extended_resources import AuthenticatedAPIConfig

config = AuthenticatedAPIConfig(
    auth_method="bearer",
    auth_config={"token": "token"}
)

result = await fetch_authenticated_api("https://api.example.com", config=config)
```

#### Import Changes

Some imports have been reorganized for better structure:

```python
# Old imports (deprecated but still work)
from web_fetch.parsers.feed_parser import parse_rss_feed

# New imports (recommended)
from web_fetch import fetch_rss_feed
from web_fetch.models.extended_resources import RSSConfig
```

### Migration Timeline

1. **Phase 1 (Immediate)**: Install extended dependencies
2. **Phase 2 (1-2 weeks)**: Update imports and basic configurations
3. **Phase 3 (1 month)**: Migrate to new authentication patterns
4. **Phase 4 (2-3 months)**: Implement advanced features and optimizations

### Testing Migration

Test your migration thoroughly:

```python
import pytest
from web_fetch import fetch_url, fetch_authenticated_api

class TestMigration:
    async def test_backward_compatibility(self):
        """Ensure old code still works."""
        result = await fetch_url("https://httpbin.org/json")
        assert result.is_success

    async def test_new_functionality(self):
        """Test new extended features."""
        config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": "test-key",
                "key_name": "X-API-Key",
                "location": "header"
            }
        )

        # This should work with the new system
        result = await fetch_authenticated_api("https://httpbin.org/headers", config=config)
        assert result.is_success

    async def test_performance_comparison(self):
        """Compare performance between old and new approaches."""
        import time

        # Test old approach
        start = time.time()
        old_result = await fetch_url("https://httpbin.org/json")
        old_time = time.time() - start

        # Test new approach
        start = time.time()
        new_result = await fetch_authenticated_api("https://httpbin.org/json")
        new_time = time.time() - start

        # New approach should be comparable or better
        assert new_time <= old_time * 1.5  # Allow 50% overhead for new features
```
