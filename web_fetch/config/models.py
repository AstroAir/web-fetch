"""
Configuration models for web_fetch.

This module defines all configuration data models with validation and defaults.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CacheBackend(str, Enum):
    """Cache backend types."""

    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DISABLED = "disabled"


class Environment(str, Enum):
    """Application environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = Field(default=LogLevel.INFO, description="Default logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )
    file_path: Optional[Path] = Field(default=None, description="Log file path")
    max_file_size: int = Field(
        default=10 * 1024 * 1024, description="Max log file size in bytes"
    )
    backup_count: int = Field(default=5, description="Number of backup log files")
    enable_console: bool = Field(default=True, description="Enable console logging")
    enable_file: bool = Field(default=False, description="Enable file logging")
    enable_structured: bool = Field(
        default=False, description="Enable structured JSON logging"
    )

    # Component-specific log levels
    component_levels: Dict[str, LogLevel] = Field(
        default_factory=dict, description="Per-component log levels"
    )


class SecurityConfig(BaseModel):
    """Security configuration."""

    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    ssl_cert_path: Optional[Path] = Field(
        default=None, description="Custom SSL certificate path"
    )
    ssl_key_path: Optional[Path] = Field(
        default=None, description="Custom SSL key path"
    )
    ca_bundle_path: Optional[Path] = Field(
        default=None, description="Custom CA bundle path"
    )

    # Request security
    max_redirects: int = Field(
        default=10, description="Maximum number of redirects to follow"
    )
    max_response_size: int = Field(
        default=100 * 1024 * 1024, description="Maximum response size in bytes"
    )
    allowed_schemes: List[str] = Field(
        default=["http", "https"], description="Allowed URL schemes"
    )
    blocked_hosts: List[str] = Field(
        default_factory=list, description="Blocked hostnames"
    )
    allowed_hosts: Optional[List[str]] = Field(
        default=None, description="Allowed hostnames (whitelist)"
    )

    # Authentication security
    mask_credentials: bool = Field(default=True, description="Mask credentials in logs")
    credential_cache_ttl: int = Field(
        default=3600, description="Credential cache TTL in seconds"
    )


class PerformanceConfig(BaseModel):
    """Performance configuration."""

    # Connection settings
    max_connections: int = Field(default=100, description="Maximum total connections")
    max_connections_per_host: int = Field(
        default=10, description="Maximum connections per host"
    )
    connection_timeout: float = Field(
        default=10.0, description="Connection timeout in seconds"
    )
    read_timeout: float = Field(default=30.0, description="Read timeout in seconds")
    total_timeout: float = Field(
        default=60.0, description="Total request timeout in seconds"
    )

    # Concurrency settings
    max_concurrent_requests: int = Field(
        default=50, description="Maximum concurrent requests"
    )
    semaphore_timeout: float = Field(
        default=30.0, description="Semaphore acquisition timeout"
    )

    # Retry settings
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Base retry delay in seconds")
    retry_backoff_factor: float = Field(
        default=2.0, description="Retry backoff multiplier"
    )

    # Memory settings
    chunk_size: int = Field(
        default=8192, description="Default chunk size for streaming"
    )
    buffer_size: int = Field(
        default=64 * 1024, description="Buffer size for I/O operations"
    )

    # Cache settings
    enable_dns_cache: bool = Field(default=True, description="Enable DNS caching")
    dns_cache_ttl: int = Field(default=300, description="DNS cache TTL in seconds")


class FeatureFlags(BaseModel):
    """Feature flags for enabling/disabling functionality."""

    # Core features
    enable_caching: bool = Field(default=True, description="Enable response caching")
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    enable_circuit_breaker: bool = Field(
        default=True, description="Enable circuit breaker"
    )
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_deduplication: bool = Field(
        default=True, description="Enable request deduplication"
    )

    # Advanced features
    enable_compression: bool = Field(
        default=True, description="Enable response compression"
    )
    enable_http2: bool = Field(default=True, description="Enable HTTP/2 support")
    enable_websockets: bool = Field(
        default=True, description="Enable WebSocket support"
    )
    enable_graphql: bool = Field(default=True, description="Enable GraphQL support")

    # Content processing
    enable_content_parsing: bool = Field(
        default=True, description="Enable content parsing"
    )
    enable_image_processing: bool = Field(
        default=True, description="Enable image processing"
    )
    enable_pdf_processing: bool = Field(
        default=True, description="Enable PDF processing"
    )
    enable_js_rendering: bool = Field(
        default=False, description="Enable JavaScript rendering"
    )

    # External integrations
    enable_crawlers: bool = Field(
        default=True, description="Enable crawler integrations"
    )
    enable_ftp: bool = Field(default=True, description="Enable FTP support")


class EnvironmentConfig(BaseModel):
    """Environment-specific configuration."""

    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Current environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    testing: bool = Field(default=False, description="Enable testing mode")

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Data directory")
    cache_dir: Path = Field(default=Path("cache"), description="Cache directory")
    log_dir: Path = Field(default=Path("logs"), description="Log directory")
    temp_dir: Path = Field(default=Path("temp"), description="Temporary directory")

    @field_validator("data_dir", "cache_dir", "log_dir", "temp_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: Any) -> Path:
        """Ensure paths are Path objects."""
        return Path(v) if not isinstance(v, Path) else v

    @classmethod
    def for_environment(cls, environment: Environment) -> "GlobalConfig":
        """
        Create configuration for specific environment.

        Args:
            environment: Target environment

        Returns:
            GlobalConfig configured for the environment
        """
        if environment == Environment.DEVELOPMENT:
            return GlobalConfig(
                environment=EnvironmentConfig(
                    environment=environment,
                    debug=True
                ),
                logging=LoggingConfig(level=LogLevel.DEBUG),
                security=SecurityConfig(verify_ssl=False),
                performance=PerformanceConfig(max_concurrent_requests=5)
            )
        elif environment == Environment.TESTING:
            return GlobalConfig(
                environment=EnvironmentConfig(
                    environment=environment,
                    debug=True,
                    testing=True
                ),
                logging=LoggingConfig(level=LogLevel.DEBUG),
                security=SecurityConfig(verify_ssl=False),
                performance=PerformanceConfig(max_concurrent_requests=3)
            )
        elif environment == Environment.PRODUCTION:
            return GlobalConfig(
                environment=EnvironmentConfig(
                    environment=environment,
                    debug=False
                ),
                logging=LoggingConfig(level=LogLevel.WARNING),
                security=SecurityConfig(verify_ssl=True),
                performance=PerformanceConfig(max_concurrent_requests=50)
            )
        elif environment == Environment.STAGING:
            return GlobalConfig(
                environment=EnvironmentConfig(
                    environment=environment,
                    debug=False
                ),
                logging=LoggingConfig(level=LogLevel.INFO),
                security=SecurityConfig(verify_ssl=True),
                performance=PerformanceConfig(max_concurrent_requests=20)
            )
        else:  # pragma: no cover
            # Defensive programming - handle any future enum values
            return GlobalConfig(  # type: ignore[unreachable]
                environment=EnvironmentConfig(environment=environment)
            )




class GlobalConfig(BaseModel):
    """Global configuration container."""

    # Sub-configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)

    # Global settings
    user_agent: str = Field(
        default="WebFetch/0.1.0 (https://github.com/web-fetch/web-fetch)",
        description="Default User-Agent header",
    )

    # Custom settings
    custom: Dict[str, Any] = Field(
        default_factory=dict, description="Custom configuration values"
    )

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True
    )
