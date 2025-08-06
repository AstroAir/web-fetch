#!/usr/bin/env python3
"""
Advanced configuration examples for the web-fetch library.

This script demonstrates various configuration patterns including:
- Environment variable configuration
- Configuration files (JSON, YAML, TOML)
- Complex multi-layered configurations
- Dynamic configuration updates
- Configuration validation and best practices
"""

import asyncio
import json
import os
import tempfile

from web_fetch import (
    WebFetcher,
    FetchConfig,
    FetchRequest,
    CacheConfig,
    RateLimitConfig,
    RequestHeaders,
)


def example_environment_variables() -> None:
    """Demonstrate configuration via environment variables."""
    print("=== Environment Variable Configuration ===\n")
    
    # Set example environment variables
    env_vars = {
        'WEB_FETCH_TIMEOUT': '30',
        'WEB_FETCH_MAX_RETRIES': '5',
        'WEB_FETCH_CONCURRENT_REQUESTS': '10',
        'WEB_FETCH_VERIFY_SSL': 'true',
        'WEB_FETCH_USER_AGENT': 'MyApp/2.0',
        'WEB_FETCH_CACHE_TTL': '300',
        'WEB_FETCH_RATE_LIMIT_RPS': '10.0',
    }
    
    print("Example environment variables:")
    for key, value in env_vars.items():
        print(f"export {key}={value}")
        os.environ[key] = value  # Set for demonstration
    
    print("\nConfiguration from environment:")
    
    # Create configuration from environment variables
    config = FetchConfig(
        total_timeout=float(os.getenv('WEB_FETCH_TIMEOUT', '30')),
        max_retries=int(os.getenv('WEB_FETCH_MAX_RETRIES', '3')),
        max_concurrent_requests=int(os.getenv('WEB_FETCH_CONCURRENT_REQUESTS', '10')),
        verify_ssl=os.getenv('WEB_FETCH_VERIFY_SSL', 'true').lower() == 'true',
    )
    
    # Custom headers from environment
    user_agent = os.getenv('WEB_FETCH_USER_AGENT', 'WebFetch/1.0')
    headers = RequestHeaders(user_agent=user_agent)
    # Use headers to avoid unused warning
    if headers.user_agent:
        pass
    
    # Cache configuration
    cache_config = CacheConfig(
        ttl_seconds=int(os.getenv('WEB_FETCH_CACHE_TTL', '300')),
        max_size=int(os.getenv('WEB_FETCH_CACHE_SIZE', '100'))
    )
    
    # Rate limiting configuration
    rate_limit_config = RateLimitConfig(
        requests_per_second=float(os.getenv('WEB_FETCH_RATE_LIMIT_RPS', '5.0')),
        burst_size=int(os.getenv('WEB_FETCH_RATE_LIMIT_BURST', '10'))
    )
    
    print(f"Timeout: {config.total_timeout}s")
    print(f"Max retries: {config.max_retries}")
    print(f"Concurrent requests: {config.max_concurrent_requests}")
    print(f"SSL verification: {config.verify_ssl}")
    print(f"User agent: {user_agent}")
    print(f"Cache TTL: {cache_config.ttl_seconds}s")
    print(f"Rate limit: {rate_limit_config.requests_per_second} req/s")
    print()


def example_json_configuration() -> None:
    """Demonstrate configuration via JSON files."""
    print("=== JSON Configuration File ===\n")
    
    # Create example JSON configuration
    config_data = {
        "http": {
            "timeout": {
                "total": 60.0,
                "connect": 10.0,
                "read": 30.0
            },
            "retries": {
                "max_retries": 3,
                "retry_delay": 1.0,
                "strategy": "exponential"
            },
            "concurrency": {
                "max_concurrent_requests": 15,
                "max_connections_per_host": 5
            },
            "ssl": {
                "verify": True,
                "cert_file": None,
                "key_file": None
            }
        },
        "headers": {
            "user_agent": "MyApp/1.0 (Advanced Config)",
            "accept": "application/json, text/html",
            "custom_headers": {
                "X-API-Version": "v2",
                "X-Client-ID": "advanced-client"
            }
        },
        "caching": {
            "enabled": True,
            "ttl_seconds": 600,
            "max_size": 200,
            "compression": True
        },
        "rate_limiting": {
            "enabled": True,
            "requests_per_second": 20.0,
            "burst_size": 50,
            "per_host": True
        }
    }
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f, indent=2)
        config_file = f.name
    
    print(f"Created configuration file: {config_file}")
    print("Configuration content:")
    print(json.dumps(config_data, indent=2))
    
    # Load and parse configuration
    with open(config_file, 'r') as f:
        loaded_config = json.load(f)
    
    # Create FetchConfig from JSON
    http_config = loaded_config['http']
    config = FetchConfig(
        total_timeout=float(http_config['timeout']['total']),
        connect_timeout=float(http_config['timeout']['connect']),
        read_timeout=float(http_config['timeout']['read']),
        max_retries=int(http_config['retries']['max_retries']),
        retry_delay=float(http_config['retries']['retry_delay']),
        max_concurrent_requests=int(http_config['concurrency']['max_concurrent_requests']),
        verify_ssl=bool(http_config['ssl']['verify'])
    )
    
    print(f"\nParsed configuration:")
    print(f"Total timeout: {config.total_timeout}s")
    print(f"Max retries: {config.max_retries}")
    print(f"Concurrent requests: {config.max_concurrent_requests}")
    
    # Cleanup
    os.unlink(config_file)
    print()


def example_yaml_configuration() -> None:
    """Demonstrate YAML configuration (conceptual)."""
    print("=== YAML Configuration Example ===\n")
    
    yaml_content = """
# Web-fetch configuration file
web_fetch:
  http:
    timeout:
      total: 45.0
      connect: 15.0
      read: 30.0
    retries:
      max_retries: 5
      retry_delay: 2.0
      strategy: exponential
      backoff_factor: 2.0
    concurrency:
      max_concurrent_requests: 20
      semaphore_timeout: 60.0
    
  headers:
    user_agent: "MyApp/1.0 (YAML Config)"
    default_headers:
      Accept: "application/json"
      Accept-Encoding: "gzip, deflate"
      Connection: "keep-alive"
    
  caching:
    enabled: true
    backend: "memory"  # memory, redis, file
    ttl_seconds: 900
    max_size: 500
    compression: true
    
  rate_limiting:
    enabled: true
    requests_per_second: 15.0
    burst_size: 30
    per_host: true
    
  logging:
    level: "INFO"
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
  features:
    enable_metrics: true
    enable_deduplication: true
    enable_circuit_breaker: true
"""
    
    print("Example YAML configuration:")
    print(yaml_content)
    
    # Note: In a real implementation, you would use PyYAML:
    # import yaml
    # config_dict = yaml.safe_load(yaml_content)
    # Then parse the dictionary similar to JSON example
    
    print("Note: Install PyYAML to use YAML configuration files")
    print("pip install PyYAML")
    print()


def example_toml_configuration() -> None:
    """Demonstrate TOML configuration (conceptual)."""
    print("=== TOML Configuration Example ===\n")
    
    toml_content = """
[web_fetch]
title = "Web-fetch Configuration"
version = "1.0"

[web_fetch.http]
total_timeout = 50.0
connect_timeout = 12.0
read_timeout = 35.0
max_retries = 4
retry_delay = 1.5
max_concurrent_requests = 25
verify_ssl = true

[web_fetch.headers]
user_agent = "MyApp/1.0 (TOML Config)"
accept = "application/json, text/plain"

[web_fetch.headers.custom]
"X-API-Key" = "your-api-key"
"X-Client-Version" = "2.1.0"

[web_fetch.caching]
enabled = true
ttl_seconds = 1200
max_size = 300
compression = true

[web_fetch.rate_limiting]
enabled = true
requests_per_second = 12.5
burst_size = 25
per_host = true

[web_fetch.features]
enable_metrics = true
enable_deduplication = false
enable_circuit_breaker = true
"""
    
    print("Example TOML configuration:")
    print(toml_content)
    
    print("Note: Install tomli/tomllib to use TOML configuration files")
    print("pip install tomli  # For Python < 3.11")
    print("# tomllib is built-in for Python 3.11+")
    print()


async def example_dynamic_configuration() -> None:
    """Demonstrate dynamic configuration updates."""
    print("=== Dynamic Configuration Updates ===\n")
    
    # Start with basic configuration
    initial_config = FetchConfig(
        total_timeout=10.0,
        max_retries=2,
        max_concurrent_requests=5
    )
    
    print("Initial configuration:")
    print(f"Timeout: {initial_config.total_timeout}s")
    print(f"Retries: {initial_config.max_retries}")
    print(f"Concurrent: {initial_config.max_concurrent_requests}")
    
    async with WebFetcher(initial_config) as fetcher:
        # Make a request with initial config
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)
        request = FetchRequest(url=url_adapter.validate_python("https://httpbin.org/delay/1"))
        result = await fetcher.fetch_single(request)
        print(f"First request time: {result.response_time:.2f}s")
        
        # Update configuration dynamically (conceptual)
        # Note: In practice, you'd create a new fetcher instance
        updated_config = FetchConfig(
            total_timeout=30.0,
            max_retries=5,
            max_concurrent_requests=10
        )
        
        print("\nUpdated configuration:")
        print(f"Timeout: {updated_config.total_timeout}s")
        print(f"Retries: {updated_config.max_retries}")
        print(f"Concurrent: {updated_config.max_concurrent_requests}")
    
    # Use updated configuration
    async with WebFetcher(updated_config) as fetcher:
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)
        request = FetchRequest(url=url_adapter.validate_python("https://httpbin.org/delay/2"))
        result = await fetcher.fetch_single(request)
        print(f"Second request time: {result.response_time:.2f}s")
    
    print()


async def example_profile_based_configuration() -> None:
    """Demonstrate profile-based configuration for different environments."""
    print("=== Profile-Based Configuration ===\n")
    
    # Define configuration profiles
    profiles = {
        "development": {
            "timeout": 60.0,
            "retries": 1,
            "concurrent": 3,
            "verify_ssl": False,
            "verbose": True
        },
        "testing": {
            "timeout": 30.0,
            "retries": 2,
            "concurrent": 5,
            "verify_ssl": True,
            "verbose": False
        },
        "production": {
            "timeout": 15.0,
            "retries": 5,
            "concurrent": 20,
            "verify_ssl": True,
            "verbose": False
        }
    }
    
    # Select profile based on environment
    current_profile = os.getenv('WEB_FETCH_PROFILE', 'development')
    profile_config = profiles.get(current_profile, profiles['development'])
    
    print(f"Active profile: {current_profile}")
    print("Profile configuration:")
    for key, value in profile_config.items():
        print(f"  {key}: {value}")
    
    # Create configuration from profile
    config = FetchConfig(
        total_timeout=float(profile_config['timeout']),
        max_retries=int(profile_config['retries']),
        max_concurrent_requests=int(profile_config['concurrent']),
        verify_ssl=bool(profile_config['verify_ssl'])
    )
    
    # Test with profile configuration
    async with WebFetcher(config) as fetcher:
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)
        request = FetchRequest(url=url_adapter.validate_python("https://httpbin.org/get"))
        result = await fetcher.fetch_single(request)
        print(f"\nProfile test result: {result.status_code} in {result.response_time:.2f}s")
    
    print()


async def example_configuration_validation() -> None:
    """Demonstrate configuration validation and error handling."""
    print("=== Configuration Validation ===\n")
    
    # Valid configuration
    try:
        valid_config = FetchConfig(
            total_timeout=30.0,
            connect_timeout=10.0,
            read_timeout=20.0,
            max_retries=3,
            retry_delay=1.0,
            max_concurrent_requests=10,
            verify_ssl=True
        )
        print("✓ Valid configuration created successfully")
        print(f"  Total timeout: {valid_config.total_timeout}s")
        print(f"  Connect timeout: {valid_config.connect_timeout}s")
        print(f"  Read timeout: {valid_config.read_timeout}s")
    except Exception as e:
        print(f"✗ Configuration error: {e}")
    
    # Invalid configurations (examples of what might fail)
    invalid_configs = [
        {"total_timeout": -5.0, "description": "Negative timeout"},
        {"max_retries": -1, "description": "Negative retries"},
        {"max_concurrent_requests": 0, "description": "Zero concurrency"},
        {"retry_delay": -1.0, "description": "Negative retry delay"},
    ]
    
    print("\nTesting invalid configurations:")
    for invalid in invalid_configs:
        desc = invalid.get("description", "Invalid config")
        invalid_copy = {k: v for k, v in invalid.items() if k != "description"}
        try:
            config = FetchConfig(**invalid_copy)  # type: ignore[arg-type]
            # use config to avoid unused warning
            _ = config.total_timeout
            print(f"✗ {desc}: Should have failed but didn't")
        except Exception as e:
            print(f"✓ {desc}: Correctly rejected - {e}")
    
    print()


def example_configuration_best_practices() -> None:
    """Demonstrate configuration best practices."""
    print("=== Configuration Best Practices ===\n")
    
    print("1. Environment-Specific Configurations:")
    print("   - Use different timeouts for dev/test/prod")
    print("   - Adjust concurrency based on target servers")
    print("   - Enable/disable SSL verification appropriately")
    print()
    
    print("2. Timeout Configuration Guidelines:")
    print("   - Connect timeout: 5-15 seconds")
    print("   - Read timeout: 15-60 seconds")
    print("   - Total timeout: Connect + Read + buffer")
    print()
    
    print("3. Retry Strategy Recommendations:")
    print("   - Use exponential backoff for most cases")
    print("   - Limit retries to 3-5 attempts")
    print("   - Consider the target server's capacity")
    print()
    
    print("4. Concurrency Guidelines:")
    print("   - Start with 5-10 concurrent requests")
    print("   - Monitor target server response times")
    print("   - Adjust based on rate limiting")
    print()
    
    print("5. Security Considerations:")
    print("   - Always verify SSL in production")
    print("   - Use environment variables for sensitive data")
    print("   - Rotate API keys regularly")
    print()
    
    print("6. Performance Optimization:")
    print("   - Enable connection pooling")
    print("   - Use appropriate cache TTL values")
    print("   - Monitor and adjust rate limits")
    print()


async def main() -> None:
    """Run all configuration examples."""
    print("Web Fetch Library - Advanced Configuration Examples")
    print("=" * 60)
    print()
    
    try:
        example_environment_variables()
        example_json_configuration()
        example_yaml_configuration()
        example_toml_configuration()
        await example_dynamic_configuration()
        await example_profile_based_configuration()
        await example_configuration_validation()
        example_configuration_best_practices()
        
        print("🎉 All configuration examples completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
