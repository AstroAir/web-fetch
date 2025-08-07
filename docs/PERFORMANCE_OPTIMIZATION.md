# Performance Optimization Guide

## Overview

This guide provides comprehensive strategies for optimizing the performance of the Web-Fetch MCP Server and the underlying web-fetch library.

## Performance Features

### Built-in Optimizations

The web-fetch library includes numerous performance optimizations out of the box:

- **Connection Pooling**: Reuse HTTP connections to reduce overhead
- **DNS Caching**: Cache DNS lookups to avoid repeated resolution
- **Response Compression**: Automatic gzip/deflate decompression
- **Keep-Alive**: Maintain persistent connections
- **Request Deduplication**: Avoid duplicate requests
- **Circuit Breaker**: Prevent cascading failures
- **Adaptive Retry**: Intelligent retry strategies

### MCP Server Performance Tools

The MCP server provides dedicated performance optimization tools:

#### performance_optimize

Optimize system performance with various strategies:

```python
# Enable caching
await mcp.call_tool("performance_optimize", {
    "action": "enable_cache",
    "config": {
        "max_size": 1000,
        "ttl": 3600,
        "enable_compression": True
    }
})

# Configure connection pooling
await mcp.call_tool("performance_optimize", {
    "action": "configure_pool",
    "config": {
        "max_connections": 100,
        "max_per_host": 30,
        "dns_cache_ttl": 300,
        "keepalive_timeout": 30
    }
})

# Optimize memory usage
await mcp.call_tool("performance_optimize", {
    "action": "optimize_memory"
})

# Tune concurrency
await mcp.call_tool("performance_optimize", {
    "action": "tune_concurrency",
    "config": {
        "max_concurrent": 50,
        "rate_limit": 10.0,
        "adaptive": True
    }
})
```

#### performance_monitor

Monitor system performance and resource usage:

```python
# System metrics
system_metrics = await mcp.call_tool("performance_monitor", {
    "metric_type": "system"
})

# Cache performance
cache_metrics = await mcp.call_tool("performance_monitor", {
    "metric_type": "cache"
})

# Connection pool stats
connection_metrics = await mcp.call_tool("performance_monitor", {
    "metric_type": "connections"
})

# Memory usage
memory_metrics = await mcp.call_tool("performance_monitor", {
    "metric_type": "memory"
})
```

## Configuration Optimization

### FetchConfig Tuning

```python
from web_fetch import FetchConfig

# High-performance configuration
config = FetchConfig(
    # Connection settings
    max_connections=100,
    max_connections_per_host=30,
    connection_timeout=10.0,
    read_timeout=30.0,
    total_timeout=60.0,
    
    # Concurrency
    max_concurrent_requests=50,
    semaphore_timeout=30.0,
    
    # Retry strategy
    max_retries=3,
    retry_delay=1.0,
    retry_backoff_factor=2.0,
    
    # Memory optimization
    chunk_size=8192,
    buffer_size=64 * 1024,
    
    # DNS caching
    enable_dns_cache=True,
    dns_cache_ttl=300
)
```

### Cache Configuration

```python
from web_fetch.utils import EnhancedCacheConfig, CacheBackend

# Memory cache for development
memory_cache = EnhancedCacheConfig(
    backend=CacheBackend.MEMORY,
    max_size=1000,
    default_ttl=3600,
    enable_compression=True
)

# Redis cache for production
redis_cache = EnhancedCacheConfig(
    backend=CacheBackend.REDIS,
    redis_url="redis://localhost:6379",
    redis_db=0,
    default_ttl=3600,
    max_size=10000,
    enable_compression=True
)

# File cache for persistent storage
file_cache = EnhancedCacheConfig(
    backend=CacheBackend.FILE,
    cache_dir="/tmp/web_fetch_cache",
    default_ttl=3600,
    max_size=5000,
    enable_compression=True
)
```

## Batch Processing Optimization

### Efficient Batch Operations

```python
from web_fetch import fetch_urls
from web_fetch.models import BatchFetchRequest, FetchRequest

# Optimized batch processing
urls = ["https://example1.com", "https://example2.com", ...]

# Method 1: Simple batch
results = await fetch_urls(
    urls,
    max_concurrent=10,  # Adjust based on target server limits
    timeout=30,
    enable_caching=True
)

# Method 2: Advanced batch with prioritization
requests = [
    FetchRequest(
        url=url,
        priority=RequestPriority.HIGH if i < 5 else RequestPriority.NORMAL
    )
    for i, url in enumerate(urls)
]

batch_request = BatchFetchRequest(requests=requests)

async with WebFetcher(config) as fetcher:
    result = await fetcher.fetch_batch_optimized(batch_request)
```

### Concurrency Guidelines

- **Small targets (< 10 URLs)**: 3-5 concurrent requests
- **Medium targets (10-100 URLs)**: 5-15 concurrent requests  
- **Large targets (100+ URLs)**: 10-50 concurrent requests
- **Rate-limited APIs**: 1-5 concurrent requests

## Memory Optimization

### Memory Management Strategies

```python
import gc
import asyncio

# Periodic garbage collection
async def periodic_gc():
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        collected = gc.collect()
        print(f"Garbage collected: {collected} objects")

# Start background task
asyncio.create_task(periodic_gc())

# Manual optimization
def optimize_memory():
    # Force garbage collection
    collected = gc.collect()
    
    # Clear caches if needed
    if memory_usage_high():
        clear_caches()
    
    return collected
```

### Large File Handling

```python
# Streaming for large files
async def download_large_file(url, local_path):
    async with WebFetcher() as fetcher:
        async with fetcher.stream_download(url) as stream:
            with open(local_path, 'wb') as f:
                async for chunk in stream:
                    f.write(chunk)
                    # Optional: yield control periodically
                    if f.tell() % (1024 * 1024) == 0:  # Every MB
                        await asyncio.sleep(0)
```

## Network Optimization

### Connection Pool Tuning

```python
import aiohttp

# Optimized connector
connector = aiohttp.TCPConnector(
    limit=100,              # Total connection pool size
    limit_per_host=30,      # Max connections per host
    ttl_dns_cache=300,      # DNS cache TTL
    use_dns_cache=True,     # Enable DNS caching
    keepalive_timeout=30,   # Keep-alive timeout
    enable_cleanup_closed=True,  # Clean up closed connections
    force_close=False,      # Reuse connections
    ssl=False              # Disable SSL verification if needed
)

# Custom session with optimized settings
session = aiohttp.ClientSession(
    connector=connector,
    timeout=aiohttp.ClientTimeout(total=60, connect=10),
    headers={'User-Agent': 'WebFetch/1.0'},
    cookie_jar=aiohttp.CookieJar()
)
```

### DNS Optimization

```python
# Custom DNS resolver
import aiodns

resolver = aiodns.DNSResolver()

# Pre-resolve common domains
common_domains = ['api.example.com', 'cdn.example.com']
for domain in common_domains:
    try:
        await resolver.gethostbyname(domain, socket.AF_INET)
    except Exception:
        pass
```

## Monitoring and Profiling

### Performance Monitoring

```python
import time
import asyncio
from collections import defaultdict

class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
    
    async def monitor_request(self, url, func, *args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            success = True
        except Exception as e:
            result = None
            success = False
        finally:
            duration = time.time() - start_time
            self.metrics['response_times'].append(duration)
            self.metrics['success_rate'].append(success)
        
        return result
    
    def get_stats(self):
        response_times = self.metrics['response_times']
        success_rate = self.metrics['success_rate']
        
        return {
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'success_rate': sum(success_rate) / len(success_rate) * 100 if success_rate else 0,
            'total_requests': len(response_times)
        }

# Usage
monitor = PerformanceMonitor()

async def monitored_fetch(url):
    return await monitor.monitor_request(url, fetch_url, url)
```

### Profiling Tools

```python
import cProfile
import pstats
import io

def profile_function(func):
    """Decorator to profile function performance."""
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        print(s.getvalue())
        
        return result
    return wrapper

# Usage
@profile_function
async def batch_fetch_example():
    urls = ["https://example.com"] * 100
    return await fetch_urls(urls, max_concurrent=10)
```

## Production Deployment

### Environment Configuration

```bash
# Performance environment variables
export WEB_FETCH_MAX_CONNECTIONS=200
export WEB_FETCH_MAX_CONCURRENT=100
export WEB_FETCH_CACHE_SIZE=10000
export WEB_FETCH_DNS_CACHE_TTL=600
export WEB_FETCH_ENABLE_COMPRESSION=true

# Memory optimization
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1

# Garbage collection tuning
export PYTHONGC=1
```

### Docker Optimization

```dockerfile
FROM python:3.11-slim

# Install performance dependencies
RUN pip install psutil uvloop

# Set performance environment variables
ENV PYTHONOPTIMIZE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV WEB_FETCH_MAX_CONNECTIONS=200

# Copy and install application
COPY . /app
WORKDIR /app
RUN pip install -e .[performance]

# Use uvloop for better async performance
CMD ["python", "-c", "import uvloop; uvloop.install(); from mcp_server.server import main; main()"]
```

## Troubleshooting Performance Issues

### Common Performance Problems

1. **High Memory Usage**
   - Enable garbage collection monitoring
   - Reduce cache sizes
   - Use streaming for large files

2. **Slow Response Times**
   - Increase connection pool size
   - Reduce concurrent requests
   - Enable DNS caching

3. **Connection Timeouts**
   - Increase timeout values
   - Check network connectivity
   - Monitor connection pool usage

4. **Rate Limiting**
   - Implement exponential backoff
   - Reduce request rate
   - Use multiple IP addresses

### Performance Testing

```python
import asyncio
import time
from statistics import mean, median

async def performance_test():
    urls = ["https://httpbin.org/delay/1"] * 50
    
    start_time = time.time()
    results = await fetch_urls(urls, max_concurrent=10)
    end_time = time.time()
    
    total_time = end_time - start_time
    successful = sum(1 for r in results if r.success)
    
    print(f"Total time: {total_time:.2f}s")
    print(f"Success rate: {successful/len(results)*100:.1f}%")
    print(f"Requests per second: {len(results)/total_time:.2f}")

# Run performance test
asyncio.run(performance_test())
```

## Best Practices Summary

1. **Use connection pooling** for multiple requests
2. **Enable caching** for repeated requests
3. **Tune concurrency** based on target server limits
4. **Monitor performance** regularly
5. **Use streaming** for large files
6. **Implement circuit breakers** for reliability
7. **Profile code** to identify bottlenecks
8. **Configure timeouts** appropriately
9. **Use batch operations** when possible
10. **Monitor memory usage** and optimize as needed
