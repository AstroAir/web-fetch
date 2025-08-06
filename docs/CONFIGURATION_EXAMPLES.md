# Configuration Examples

This document provides comprehensive examples for configuring the web-fetch library in various scenarios, including environment variables, configuration files, and advanced patterns.

## Table of Contents

- [Basic Configuration](#basic-configuration)
- [Environment Variable Configuration](#environment-variable-configuration)
- [Configuration Files](#configuration-files)
- [Profile-Based Configuration](#profile-based-configuration)
- [Advanced Configuration Patterns](#advanced-configuration-patterns)
- [Configuration Validation](#configuration-validation)
- [Best Practices](#best-practices)

## Basic Configuration

### Simple Configuration Examples

```python
from web_fetch import FetchConfig, WebFetcher

# Development configuration (lenient settings)
dev_config = FetchConfig(
    total_timeout=60.0,
    max_retries=1,
    verify_ssl=False,  # For testing with self-signed certs
    max_concurrent_requests=3
)

# Production configuration (strict and robust)
prod_config = FetchConfig(
    total_timeout=15.0,
    connect_timeout=5.0,
    read_timeout=10.0,
    max_retries=5,
    retry_delay=2.0,
    max_concurrent_requests=20,
    verify_ssl=True,
    follow_redirects=True
)

# High-throughput configuration
high_throughput_config = FetchConfig(
    max_concurrent_requests=50,
    total_timeout=10.0,
    max_retries=2,
    retry_delay=0.5
)

# Memory-efficient configuration
memory_config = FetchConfig(
    max_response_size=1024*1024,  # 1MB limit
    max_concurrent_requests=5,
    enable_compression=True
)
```

### Timeout Strategy Examples

```python
# Conservative timeouts (unreliable networks)
conservative_config = FetchConfig(
    connect_timeout=30.0,
    read_timeout=60.0,
    total_timeout=120.0,
    max_retries=5,
    retry_delay=3.0
)

# Aggressive timeouts (fast APIs)
aggressive_config = FetchConfig(
    connect_timeout=3.0,
    read_timeout=5.0,
    total_timeout=10.0,
    max_retries=2,
    retry_delay=0.5
)

# Streaming-optimized timeouts
streaming_config = FetchConfig(
    connect_timeout=10.0,
    read_timeout=300.0,  # Long read timeout for streaming
    total_timeout=600.0,
    max_concurrent_requests=3
)
```

## Environment Variable Configuration

### Complete Environment Setup

```bash
#!/bin/bash
# Complete environment configuration script

# Core HTTP settings
export WEB_FETCH_TOTAL_TIMEOUT=30.0
export WEB_FETCH_CONNECT_TIMEOUT=10.0
export WEB_FETCH_READ_TIMEOUT=20.0
export WEB_FETCH_MAX_RETRIES=3
export WEB_FETCH_RETRY_DELAY=1.0
export WEB_FETCH_RETRY_STRATEGY=exponential
export WEB_FETCH_MAX_CONCURRENT=10
export WEB_FETCH_VERIFY_SSL=true
export WEB_FETCH_FOLLOW_REDIRECTS=true
export WEB_FETCH_MAX_RESPONSE_SIZE=10485760

# Headers and user agent
export WEB_FETCH_USER_AGENT="MyApp/2.0 (Production)"
export WEB_FETCH_DEFAULT_HEADERS='{"Accept": "application/json", "Accept-Encoding": "gzip"}'

# Caching configuration
export WEB_FETCH_CACHE_ENABLED=true
export WEB_FETCH_CACHE_TTL=300
export WEB_FETCH_CACHE_MAX_SIZE=1000
export WEB_FETCH_CACHE_COMPRESSION=true

# Rate limiting
export WEB_FETCH_RATE_LIMIT_ENABLED=true
export WEB_FETCH_RATE_LIMIT_RPS=15.0
export WEB_FETCH_RATE_LIMIT_BURST=30

# Advanced features
export WEB_FETCH_ENABLE_METRICS=true
export WEB_FETCH_ENABLE_DEDUPLICATION=true
export WEB_FETCH_ENABLE_CIRCUIT_BREAKER=false

# Crawler API keys
export FIRECRAWL_API_KEY="fc-your-api-key"
export SPIDER_API_KEY="your-spider-key"
export TAVILY_API_KEY="tvly-your-key"
export WEB_FETCH_PRIMARY_CRAWLER="firecrawl"

# Logging
export WEB_FETCH_LOG_LEVEL=INFO
export WEB_FETCH_LOG_FORMAT=json
```

### Environment-Based Configuration Loading

```python
import os
from web_fetch import FetchConfig, CacheConfig, RateLimitConfig

def create_config_from_env():
    """Create comprehensive configuration from environment variables."""
    
    # Basic HTTP configuration
    config = FetchConfig(
        total_timeout=float(os.getenv('WEB_FETCH_TOTAL_TIMEOUT', '30.0')),
        connect_timeout=float(os.getenv('WEB_FETCH_CONNECT_TIMEOUT', '10.0')),
        read_timeout=float(os.getenv('WEB_FETCH_READ_TIMEOUT', '20.0')),
        max_retries=int(os.getenv('WEB_FETCH_MAX_RETRIES', '3')),
        retry_delay=float(os.getenv('WEB_FETCH_RETRY_DELAY', '1.0')),
        max_concurrent_requests=int(os.getenv('WEB_FETCH_MAX_CONCURRENT', '10')),
        verify_ssl=os.getenv('WEB_FETCH_VERIFY_SSL', 'true').lower() == 'true',
        follow_redirects=os.getenv('WEB_FETCH_FOLLOW_REDIRECTS', 'true').lower() == 'true',
        max_response_size=int(os.getenv('WEB_FETCH_MAX_RESPONSE_SIZE', str(10*1024*1024)))
    )
    
    return config

def create_cache_config_from_env():
    """Create cache configuration from environment variables."""
    if not os.getenv('WEB_FETCH_CACHE_ENABLED', 'false').lower() == 'true':
        return None
    
    return CacheConfig(
        ttl_seconds=int(os.getenv('WEB_FETCH_CACHE_TTL', '300')),
        max_size=int(os.getenv('WEB_FETCH_CACHE_MAX_SIZE', '100')),
        enable_compression=os.getenv('WEB_FETCH_CACHE_COMPRESSION', 'true').lower() == 'true'
    )

def create_rate_limit_config_from_env():
    """Create rate limiting configuration from environment variables."""
    if not os.getenv('WEB_FETCH_RATE_LIMIT_ENABLED', 'false').lower() == 'true':
        return None
    
    return RateLimitConfig(
        requests_per_second=float(os.getenv('WEB_FETCH_RATE_LIMIT_RPS', '10.0')),
        burst_size=int(os.getenv('WEB_FETCH_RATE_LIMIT_BURST', '20')),
        per_host=os.getenv('WEB_FETCH_RATE_LIMIT_PER_HOST', 'true').lower() == 'true'
    )

# Usage
config = create_config_from_env()
cache_config = create_cache_config_from_env()
rate_limit_config = create_rate_limit_config_from_env()
```

## Configuration Files

### JSON Configuration Example

```json
{
  "web_fetch": {
    "profiles": {
      "development": {
        "http": {
          "timeout": {"total": 60.0, "connect": 15.0, "read": 45.0},
          "retries": {"max_retries": 1, "retry_delay": 1.0, "strategy": "linear"},
          "concurrency": {"max_concurrent_requests": 3},
          "ssl": {"verify": false}
        },
        "features": {
          "enable_metrics": true,
          "enable_deduplication": false,
          "enable_circuit_breaker": false
        }
      },
      "testing": {
        "http": {
          "timeout": {"total": 30.0, "connect": 10.0, "read": 20.0},
          "retries": {"max_retries": 2, "retry_delay": 1.0, "strategy": "exponential"},
          "concurrency": {"max_concurrent_requests": 5},
          "ssl": {"verify": true}
        },
        "features": {
          "enable_metrics": true,
          "enable_deduplication": true,
          "enable_circuit_breaker": false
        }
      },
      "production": {
        "http": {
          "timeout": {"total": 15.0, "connect": 5.0, "read": 10.0},
          "retries": {"max_retries": 5, "retry_delay": 2.0, "strategy": "exponential"},
          "concurrency": {"max_concurrent_requests": 20},
          "ssl": {"verify": true}
        },
        "caching": {
          "enabled": true,
          "ttl_seconds": 600,
          "max_size": 1000,
          "compression": true
        },
        "rate_limiting": {
          "enabled": true,
          "requests_per_second": 20.0,
          "burst_size": 50,
          "per_host": true
        },
        "features": {
          "enable_metrics": true,
          "enable_deduplication": true,
          "enable_circuit_breaker": true
        }
      }
    },
    "headers": {
      "user_agent": "MyApp/1.0",
      "default_headers": {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive"
      }
    }
  }
}
```

### YAML Configuration Example

```yaml
web_fetch:
  profiles:
    development:
      http:
        timeout:
          total: 60.0
          connect: 15.0
          read: 45.0
        retries:
          max_retries: 1
          retry_delay: 1.0
          strategy: linear
        concurrency:
          max_concurrent_requests: 3
        ssl:
          verify: false
      features:
        enable_metrics: true
        enable_deduplication: false
        enable_circuit_breaker: false
    
    production:
      http:
        timeout:
          total: 15.0
          connect: 5.0
          read: 10.0
        retries:
          max_retries: 5
          retry_delay: 2.0
          strategy: exponential
        concurrency:
          max_concurrent_requests: 20
        ssl:
          verify: true
      caching:
        enabled: true
        ttl_seconds: 600
        max_size: 1000
        compression: true
      rate_limiting:
        enabled: true
        requests_per_second: 20.0
        burst_size: 50
        per_host: true
      features:
        enable_metrics: true
        enable_deduplication: true
        enable_circuit_breaker: true
  
  headers:
    user_agent: "MyApp/1.0"
    default_headers:
      Accept: "application/json"
      Accept-Encoding: "gzip, deflate"
      Connection: "keep-alive"
```

### Configuration File Loading

```python
import json
import yaml
from pathlib import Path
from web_fetch import FetchConfig

def load_json_config(file_path: str, profile: str = "production"):
    """Load configuration from JSON file."""
    with open(file_path, 'r') as f:
        config_data = json.load(f)
    
    profile_config = config_data['web_fetch']['profiles'][profile]
    http_config = profile_config['http']
    
    return FetchConfig(
        total_timeout=http_config['timeout']['total'],
        connect_timeout=http_config['timeout']['connect'],
        read_timeout=http_config['timeout']['read'],
        max_retries=http_config['retries']['max_retries'],
        retry_delay=http_config['retries']['retry_delay'],
        max_concurrent_requests=http_config['concurrency']['max_concurrent_requests'],
        verify_ssl=http_config['ssl']['verify']
    )

def load_yaml_config(file_path: str, profile: str = "production"):
    """Load configuration from YAML file."""
    with open(file_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    profile_config = config_data['web_fetch']['profiles'][profile]
    http_config = profile_config['http']
    
    return FetchConfig(
        total_timeout=http_config['timeout']['total'],
        connect_timeout=http_config['timeout']['connect'],
        read_timeout=http_config['timeout']['read'],
        max_retries=http_config['retries']['max_retries'],
        retry_delay=http_config['retries']['retry_delay'],
        max_concurrent_requests=http_config['concurrency']['max_concurrent_requests'],
        verify_ssl=http_config['ssl']['verify']
    )

# Usage
config = load_json_config('config.json', 'production')
# or
config = load_yaml_config('config.yaml', 'development')
```

## Profile-Based Configuration

### Dynamic Profile Selection

```python
import os
from web_fetch import FetchConfig

class ConfigurationManager:
    """Manages configuration profiles and dynamic switching."""

    def __init__(self):
        self.profiles = {
            "development": {
                "timeout": 60.0,
                "retries": 1,
                "concurrent": 3,
                "verify_ssl": False,
                "log_level": "DEBUG"
            },
            "testing": {
                "timeout": 30.0,
                "retries": 2,
                "concurrent": 5,
                "verify_ssl": True,
                "log_level": "INFO"
            },
            "staging": {
                "timeout": 20.0,
                "retries": 3,
                "concurrent": 10,
                "verify_ssl": True,
                "log_level": "INFO"
            },
            "production": {
                "timeout": 15.0,
                "retries": 5,
                "concurrent": 20,
                "verify_ssl": True,
                "log_level": "WARNING"
            }
        }

    def get_config(self, profile: str = None) -> FetchConfig:
        """Get configuration for specified profile."""
        if profile is None:
            profile = os.getenv('WEB_FETCH_PROFILE', 'production')

        if profile not in self.profiles:
            raise ValueError(f"Unknown profile: {profile}")

        profile_data = self.profiles[profile]

        return FetchConfig(
            total_timeout=profile_data["timeout"],
            max_retries=profile_data["retries"],
            max_concurrent_requests=profile_data["concurrent"],
            verify_ssl=profile_data["verify_ssl"]
        )

    def list_profiles(self):
        """List available profiles."""
        return list(self.profiles.keys())

# Usage
config_manager = ConfigurationManager()
config = config_manager.get_config()  # Uses WEB_FETCH_PROFILE env var
dev_config = config_manager.get_config('development')
```

### Environment-Specific Overrides

```python
def create_config_with_overrides(base_profile: str = "production"):
    """Create configuration with environment-specific overrides."""

    config_manager = ConfigurationManager()
    base_config = config_manager.get_config(base_profile)

    # Apply environment-specific overrides
    overrides = {}

    if os.getenv('WEB_FETCH_TIMEOUT_OVERRIDE'):
        overrides['total_timeout'] = float(os.getenv('WEB_FETCH_TIMEOUT_OVERRIDE'))

    if os.getenv('WEB_FETCH_RETRIES_OVERRIDE'):
        overrides['max_retries'] = int(os.getenv('WEB_FETCH_RETRIES_OVERRIDE'))

    if os.getenv('WEB_FETCH_CONCURRENT_OVERRIDE'):
        overrides['max_concurrent_requests'] = int(os.getenv('WEB_FETCH_CONCURRENT_OVERRIDE'))

    # Create new config with overrides
    config_dict = base_config.__dict__.copy()
    config_dict.update(overrides)

    return FetchConfig(**config_dict)

# Usage with overrides
# export WEB_FETCH_TIMEOUT_OVERRIDE=45.0
# export WEB_FETCH_RETRIES_OVERRIDE=7
config = create_config_with_overrides('production')
```

## Advanced Configuration Patterns

### Configuration Builder Pattern

```python
from web_fetch import FetchConfig, CacheConfig, RateLimitConfig

class ConfigBuilder:
    """Builder pattern for creating complex configurations."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder to default state."""
        self._config = {}
        self._cache_config = None
        self._rate_limit_config = None
        return self

    def with_timeouts(self, total: float, connect: float = None, read: float = None):
        """Configure timeout settings."""
        self._config['total_timeout'] = total
        if connect:
            self._config['connect_timeout'] = connect
        if read:
            self._config['read_timeout'] = read
        return self

    def with_retries(self, max_retries: int, delay: float = 1.0, strategy: str = "exponential"):
        """Configure retry settings."""
        self._config['max_retries'] = max_retries
        self._config['retry_delay'] = delay
        return self

    def with_concurrency(self, max_concurrent: int):
        """Configure concurrency settings."""
        self._config['max_concurrent_requests'] = max_concurrent
        return self

    def with_ssl(self, verify: bool = True):
        """Configure SSL settings."""
        self._config['verify_ssl'] = verify
        return self

    def with_caching(self, ttl: int = 300, max_size: int = 100, compression: bool = True):
        """Configure caching."""
        self._cache_config = CacheConfig(
            ttl_seconds=ttl,
            max_size=max_size,
            enable_compression=compression
        )
        return self

    def with_rate_limiting(self, rps: float = 10.0, burst: int = 20):
        """Configure rate limiting."""
        self._rate_limit_config = RateLimitConfig(
            requests_per_second=rps,
            burst_size=burst
        )
        return self

    def build(self) -> tuple:
        """Build the final configuration objects."""
        config = FetchConfig(**self._config)
        return config, self._cache_config, self._rate_limit_config

# Usage
builder = ConfigBuilder()
config, cache_config, rate_config = (
    builder
    .with_timeouts(total=30.0, connect=10.0, read=20.0)
    .with_retries(max_retries=3, delay=1.5)
    .with_concurrency(max_concurrent=15)
    .with_ssl(verify=True)
    .with_caching(ttl=600, max_size=200)
    .with_rate_limiting(rps=15.0, burst=30)
    .build()
)
```

### Configuration Validation

```python
from typing import Dict, Any, List
import logging

class ConfigValidator:
    """Validates configuration settings and provides recommendations."""

    def __init__(self):
        self.warnings = []
        self.errors = []

    def validate_config(self, config: FetchConfig) -> bool:
        """Validate configuration and collect issues."""
        self.warnings.clear()
        self.errors.clear()

        # Validate timeouts
        self._validate_timeouts(config)

        # Validate retries
        self._validate_retries(config)

        # Validate concurrency
        self._validate_concurrency(config)

        # Validate response limits
        self._validate_response_limits(config)

        return len(self.errors) == 0

    def _validate_timeouts(self, config: FetchConfig):
        """Validate timeout settings."""
        if config.total_timeout <= 0:
            self.errors.append("Total timeout must be positive")

        if hasattr(config, 'connect_timeout') and config.connect_timeout <= 0:
            self.errors.append("Connect timeout must be positive")

        if hasattr(config, 'read_timeout') and config.read_timeout <= 0:
            self.errors.append("Read timeout must be positive")

        # Check timeout relationships
        if (hasattr(config, 'connect_timeout') and hasattr(config, 'read_timeout') and
            config.connect_timeout + config.read_timeout > config.total_timeout):
            self.warnings.append("Total timeout should be greater than connect + read timeouts")

        # Performance recommendations
        if config.total_timeout > 120:
            self.warnings.append("Very long timeout (>120s) may cause poor user experience")

        if config.total_timeout < 5:
            self.warnings.append("Very short timeout (<5s) may cause frequent failures")

    def _validate_retries(self, config: FetchConfig):
        """Validate retry settings."""
        if config.max_retries < 0:
            self.errors.append("Max retries cannot be negative")

        if config.max_retries > 10:
            self.warnings.append("High retry count (>10) may cause long delays")

        if hasattr(config, 'retry_delay') and config.retry_delay < 0:
            self.errors.append("Retry delay cannot be negative")

    def _validate_concurrency(self, config: FetchConfig):
        """Validate concurrency settings."""
        if config.max_concurrent_requests <= 0:
            self.errors.append("Max concurrent requests must be positive")

        if config.max_concurrent_requests > 100:
            self.warnings.append("Very high concurrency (>100) may overwhelm target servers")

        if config.max_concurrent_requests == 1:
            self.warnings.append("Single concurrent request may be inefficient")

    def _validate_response_limits(self, config: FetchConfig):
        """Validate response size limits."""
        if hasattr(config, 'max_response_size') and config.max_response_size <= 0:
            self.errors.append("Max response size must be positive")

        if (hasattr(config, 'max_response_size') and
            config.max_response_size > 100 * 1024 * 1024):  # 100MB
            self.warnings.append("Very large response limit (>100MB) may cause memory issues")

    def get_report(self) -> str:
        """Get validation report."""
        report = []

        if self.errors:
            report.append("ERRORS:")
            for error in self.errors:
                report.append(f"  ❌ {error}")

        if self.warnings:
            report.append("WARNINGS:")
            for warning in self.warnings:
                report.append(f"  ⚠️  {warning}")

        if not self.errors and not self.warnings:
            report.append("✅ Configuration is valid")

        return "\n".join(report)

# Usage
validator = ConfigValidator()
config = FetchConfig(total_timeout=30.0, max_retries=3, max_concurrent_requests=10)

if validator.validate_config(config):
    print("Configuration is valid")
else:
    print("Configuration has issues:")

print(validator.get_report())
```

## Best Practices

### Configuration Management Guidelines

```python
# 1. Use environment-specific configurations
def get_environment():
    """Detect current environment."""
    return os.getenv('ENVIRONMENT', 'development').lower()

def create_environment_config():
    """Create configuration based on environment."""
    env = get_environment()

    if env == 'development':
        return FetchConfig(
            total_timeout=60.0,
            max_retries=1,
            verify_ssl=False,
            max_concurrent_requests=3
        )
    elif env == 'testing':
        return FetchConfig(
            total_timeout=30.0,
            max_retries=2,
            verify_ssl=True,
            max_concurrent_requests=5
        )
    elif env == 'production':
        return FetchConfig(
            total_timeout=15.0,
            max_retries=5,
            verify_ssl=True,
            max_concurrent_requests=20
        )
    else:
        raise ValueError(f"Unknown environment: {env}")

# 2. Configuration with fallbacks
def create_robust_config():
    """Create configuration with multiple fallback sources."""

    # Try configuration file first
    config_file = os.getenv('WEB_FETCH_CONFIG_FILE')
    if config_file and Path(config_file).exists():
        try:
            return load_json_config(config_file)
        except Exception as e:
            logging.warning(f"Failed to load config file: {e}")

    # Fall back to environment variables
    try:
        return create_config_from_env()
    except Exception as e:
        logging.warning(f"Failed to load from environment: {e}")

    # Final fallback to defaults
    return FetchConfig()

# 3. Configuration monitoring
def monitor_config_performance(config: FetchConfig):
    """Monitor configuration performance and suggest improvements."""

    # This would be implemented with actual metrics collection
    metrics = {
        'avg_response_time': 2.5,
        'success_rate': 0.95,
        'timeout_rate': 0.02,
        'retry_rate': 0.10
    }

    suggestions = []

    if metrics['timeout_rate'] > 0.05:
        suggestions.append("Consider increasing timeout values")

    if metrics['retry_rate'] > 0.15:
        suggestions.append("High retry rate - check target server reliability")

    if metrics['avg_response_time'] > 5.0:
        suggestions.append("Slow responses - consider reducing concurrency")

    return suggestions

# Usage examples
config = create_environment_config()
robust_config = create_robust_config()
suggestions = monitor_config_performance(config)
```

### Security Configuration Best Practices

```python
def create_secure_config():
    """Create configuration with security best practices."""

    return FetchConfig(
        # Always verify SSL in production
        verify_ssl=True,

        # Reasonable timeouts to prevent hanging
        total_timeout=30.0,
        connect_timeout=10.0,
        read_timeout=20.0,

        # Limit response size to prevent memory attacks
        max_response_size=10 * 1024 * 1024,  # 10MB

        # Reasonable retry limits
        max_retries=3,
        retry_delay=2.0,

        # Don't overwhelm target servers
        max_concurrent_requests=10
    )

def validate_security_config(config: FetchConfig) -> List[str]:
    """Validate configuration for security issues."""
    issues = []

    if not config.verify_ssl:
        issues.append("SSL verification is disabled - security risk")

    if config.total_timeout > 300:  # 5 minutes
        issues.append("Very long timeout may enable DoS attacks")

    if hasattr(config, 'max_response_size') and config.max_response_size > 100 * 1024 * 1024:
        issues.append("Large response limit may cause memory exhaustion")

    if config.max_concurrent_requests > 50:
        issues.append("High concurrency may overwhelm target servers")

    return issues

# Usage
secure_config = create_secure_config()
security_issues = validate_security_config(secure_config)
if security_issues:
    print("Security issues found:")
    for issue in security_issues:
        print(f"  ⚠️  {issue}")
```

## Configuration Testing

### Testing Configuration Loading

```python
import unittest
from unittest.mock import patch, mock_open
import json

class TestConfigurationLoading(unittest.TestCase):
    """Test configuration loading from various sources."""

    def test_environment_config_loading(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            'WEB_FETCH_TOTAL_TIMEOUT': '45.0',
            'WEB_FETCH_MAX_RETRIES': '7',
            'WEB_FETCH_MAX_CONCURRENT': '15',
            'WEB_FETCH_VERIFY_SSL': 'false'
        }):
            config = create_config_from_env()

            self.assertEqual(config.total_timeout, 45.0)
            self.assertEqual(config.max_retries, 7)
            self.assertEqual(config.max_concurrent_requests, 15)
            self.assertFalse(config.verify_ssl)

    def test_json_config_loading(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "web_fetch": {
                "profiles": {
                    "test": {
                        "http": {
                            "timeout": {"total": 25.0, "connect": 8.0, "read": 17.0},
                            "retries": {"max_retries": 4, "retry_delay": 1.5},
                            "concurrency": {"max_concurrent_requests": 12},
                            "ssl": {"verify": True}
                        }
                    }
                }
            }
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
            config = load_json_config('test_config.json', 'test')

            self.assertEqual(config.total_timeout, 25.0)
            self.assertEqual(config.connect_timeout, 8.0)
            self.assertEqual(config.read_timeout, 17.0)
            self.assertEqual(config.max_retries, 4)
            self.assertEqual(config.retry_delay, 1.5)
            self.assertEqual(config.max_concurrent_requests, 12)
            self.assertTrue(config.verify_ssl)

    def test_config_validation(self):
        """Test configuration validation."""
        validator = ConfigValidator()

        # Valid configuration
        valid_config = FetchConfig(
            total_timeout=30.0,
            max_retries=3,
            max_concurrent_requests=10
        )
        self.assertTrue(validator.validate_config(valid_config))
        self.assertEqual(len(validator.errors), 0)

        # Invalid configuration
        invalid_config = FetchConfig(
            total_timeout=-5.0,  # Invalid
            max_retries=-1,      # Invalid
            max_concurrent_requests=0  # Invalid
        )
        self.assertFalse(validator.validate_config(invalid_config))
        self.assertGreater(len(validator.errors), 0)

# Run tests
if __name__ == '__main__':
    unittest.main()
```

## Summary

This document provides comprehensive examples for configuring the web-fetch library:

1. **Basic Configuration**: Simple examples for common scenarios
2. **Environment Variables**: Complete environment setup and loading patterns
3. **Configuration Files**: JSON and YAML configuration with profile support
4. **Advanced Patterns**: Builder pattern, validation, and monitoring
5. **Best Practices**: Security, performance, and maintainability guidelines
6. **Testing**: Unit tests for configuration loading and validation

### Key Recommendations

- Use environment-specific profiles (dev/test/prod)
- Validate configurations before use
- Monitor configuration performance
- Follow security best practices
- Test configuration loading logic
- Use fallback mechanisms for robustness
- Document configuration options clearly
