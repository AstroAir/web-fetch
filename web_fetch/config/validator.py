"""
Configuration validator for web_fetch.

This module provides validation and sanitization of configuration values.
"""

import re
from pathlib import Path
from typing import List, Tuple

# Explicit module exports to aid static analyzers (e.g., Pylance)
__all__ = ["ConfigValidator", "ValidationError"]

from .models import (
    Environment,
    GlobalConfig,
    LogLevel,
    LoggingConfig,
    SecurityConfig,
    PerformanceConfig,
    FeatureFlags,
    EnvironmentConfig,
)


class ValidationError(Exception):
    """Configuration validation error."""

    pass


class ConfigValidator:
    """Configuration validator with comprehensive checks."""

    def __init__(self) -> None:
        """Initialize configuration validator."""
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, config: GlobalConfig) -> Tuple[bool, List[str], List[str]]:
        """
        Validate configuration and return results.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors.clear()
        self.warnings.clear()

        # Validate each section
        self._validate_logging(config.logging)
        self._validate_security(config.security)
        self._validate_performance(config.performance)
        self._validate_features(config.features)
        self._validate_environment(config.environment)
        self._validate_global_settings(config)

        return len(self.errors) == 0, self.errors.copy(), self.warnings.copy()

    def _validate_logging(self, logging_config: LoggingConfig) -> None:
        """Validate logging configuration."""
        # Validate log level
        if logging_config.level not in LogLevel:
            self.errors.append(f"Invalid log level: {logging_config.level}")

        # Validate file path
        if logging_config.file_path:
            try:
                log_path = Path(logging_config.file_path)
                if log_path.exists() and not log_path.is_file():
                    self.errors.append(f"Log path exists but is not a file: {log_path}")
                elif not log_path.parent.exists():
                    self.errors.append(
                        f"Log directory does not exist: {log_path.parent}"
                    )
            except Exception as e:
                self.errors.append(f"Invalid log file path: {e}")

        # Validate file size limits
        if logging_config.max_file_size <= 0:
            self.errors.append("Log file max size must be positive")

        if logging_config.backup_count < 0:
            self.errors.append("Log backup count cannot be negative")

        # Validate format string
        try:
            # Assign to a dummy variable to avoid 'expression value not used' warnings
            _ = logging_config.format % {
                "asctime": "2023-01-01 12:00:00",
                "name": "test",
                "levelname": "INFO",
                "message": "test",
            }
        except (KeyError, ValueError) as e:
            self.errors.append(f"Invalid log format string: {e}")

    def _validate_security(self, security_config: SecurityConfig) -> None:
        """Validate security configuration."""
        # Validate SSL certificate paths
        if security_config.ssl_cert_path:
            cert_path = Path(security_config.ssl_cert_path)
            if not cert_path.exists():
                self.errors.append(f"SSL certificate file not found: {cert_path}")

        if security_config.ssl_key_path:
            key_path = Path(security_config.ssl_key_path)
            if not key_path.exists():
                self.errors.append(f"SSL key file not found: {key_path}")

        if security_config.ca_bundle_path:
            ca_path = Path(security_config.ca_bundle_path)
            if not ca_path.exists():
                self.errors.append(f"CA bundle file not found: {ca_path}")

        # Validate redirect limits
        if security_config.max_redirects < 0:
            self.errors.append("Max redirects cannot be negative")
        elif security_config.max_redirects > 50:
            self.warnings.append("Max redirects is very high, consider reducing")

        # Validate response size
        if security_config.max_response_size <= 0:
            self.errors.append("Max response size must be positive")

        # Validate URL schemes
        valid_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}
        for scheme in security_config.allowed_schemes:
            if scheme.lower() not in valid_schemes:
                self.warnings.append(f"Unusual URL scheme allowed: {scheme}")

        # Validate hostnames
        for host in security_config.blocked_hosts:
            if not self._is_valid_hostname(host):
                self.errors.append(f"Invalid blocked hostname: {host}")

        if security_config.allowed_hosts:
            for host in security_config.allowed_hosts:
                if not self._is_valid_hostname(host):
                    self.errors.append(f"Invalid allowed hostname: {host}")

    def _validate_performance(self, performance_config: PerformanceConfig) -> None:
        """Validate performance configuration."""
        # Validate connection limits
        if performance_config.max_connections <= 0:
            self.errors.append("Max connections must be positive")

        if performance_config.max_connections_per_host <= 0:
            self.errors.append("Max connections per host must be positive")

        if performance_config.max_concurrent_requests <= 0:
            self.errors.append("Max concurrent requests must be positive")

        if (
            performance_config.max_connections_per_host
            > performance_config.max_connections
        ):
            self.warnings.append(
                "Max connections per host exceeds total max connections"
            )

        # Validate timeouts
        timeouts = [
            ("connection_timeout", performance_config.connection_timeout),
            ("read_timeout", performance_config.read_timeout),
            ("total_timeout", performance_config.total_timeout),
            ("semaphore_timeout", performance_config.semaphore_timeout),
        ]

        for name, timeout in timeouts:
            if timeout <= 0:
                self.errors.append(f"{name} must be positive")
            elif timeout > 300:  # 5 minutes
                self.warnings.append(f"{name} is very high: {timeout}s")

        # Validate retry settings
        if performance_config.max_retries < 0:
            self.errors.append("Max retries cannot be negative")
        elif performance_config.max_retries > 10:
            self.warnings.append("Max retries is very high, consider reducing")

        if performance_config.retry_delay <= 0:
            self.errors.append("Retry delay must be positive")

        if performance_config.retry_backoff_factor < 1:
            self.errors.append("Retry backoff factor must be >= 1")

        # Validate memory settings
        if performance_config.chunk_size <= 0:
            self.errors.append("Chunk size must be positive")
        elif performance_config.chunk_size < 1024:
            self.warnings.append("Chunk size is very small, may impact performance")

        if performance_config.buffer_size <= 0:
            self.errors.append("Buffer size must be positive")

        # Validate cache settings
        if performance_config.dns_cache_ttl < 0:
            self.errors.append("DNS cache TTL cannot be negative")

    def _validate_features(self, features_config: FeatureFlags) -> None:
        """Validate feature flags."""
        # Check for conflicting features
        if not features_config.enable_caching and features_config.enable_deduplication:
            self.warnings.append(
                "Deduplication without caching may have limited effectiveness"
            )

        if features_config.enable_js_rendering:
            self.warnings.append(
                "JavaScript rendering is experimental and may impact performance"
            )

    def _validate_environment(self, env_config: EnvironmentConfig) -> None:
        """Validate environment configuration."""
        # Validate environment
        if env_config.environment not in Environment:
            self.errors.append(f"Invalid environment: {env_config.environment}")

        # Validate directories
        directories = [
            ("data_dir", env_config.data_dir),
            ("cache_dir", env_config.cache_dir),
            ("log_dir", env_config.log_dir),
            ("temp_dir", env_config.temp_dir),
        ]

        for name, directory in directories:
            try:
                dir_path = Path(directory)
                if dir_path.exists() and not dir_path.is_dir():
                    self.errors.append(
                        f"{name} exists but is not a directory: {dir_path}"
                    )
            except Exception as e:
                self.errors.append(f"Invalid {name}: {e}")

    def _validate_global_settings(self, config: GlobalConfig) -> None:
        """Validate global settings."""
        # Validate User-Agent
        if not config.user_agent or len(config.user_agent.strip()) == 0:
            self.errors.append("User-Agent cannot be empty")
        elif len(config.user_agent) > 500:
            self.warnings.append("User-Agent is very long")

    def _is_valid_hostname(self, hostname: str) -> bool:
        """Check if hostname is valid."""
        if not hostname or len(hostname) > 253:
            return False

        # Allow wildcards
        if hostname.startswith("*."):
            hostname = hostname[2:]

        # Basic hostname validation
        hostname_pattern = re.compile(
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        )

        return bool(hostname_pattern.match(hostname))

    def sanitize_config(self, config: GlobalConfig) -> GlobalConfig:
        """
        Sanitize configuration by applying safe defaults and corrections.

        Args:
            config: Configuration to sanitize

        Returns:
            Sanitized configuration
        """
        # Create a copy to avoid modifying the original
        config_dict = config.model_dump()

        # Sanitize performance settings
        perf = config_dict.get("performance", {})

        # Ensure reasonable connection limits
        if perf.get("max_connections", 0) > 1000:
            perf["max_connections"] = 1000

        if perf.get("max_connections_per_host", 0) > perf.get("max_connections", 100):
            perf["max_connections_per_host"] = min(perf.get("max_connections", 100), 50)

        # Ensure reasonable timeouts
        for timeout_key in ["connection_timeout", "read_timeout", "total_timeout"]:
            if perf.get(timeout_key, 0) > 300:
                perf[timeout_key] = 300

        # Ensure reasonable retry settings
        if perf.get("max_retries", 0) > 10:
            perf["max_retries"] = 10

        # Sanitize security settings
        security = config_dict.get("security", {})

        # Ensure reasonable redirect limit
        if security.get("max_redirects", 0) > 50:
            security["max_redirects"] = 50

        # Create new config with sanitized values
        return GlobalConfig.model_construct(**config_dict)
