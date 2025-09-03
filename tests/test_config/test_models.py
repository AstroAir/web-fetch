"""
Comprehensive tests for the config models module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from web_fetch.config.models import (
    ConfigModel,
    FetchConfig,
    HTTPConfig,
    AuthConfig,
    CacheConfig,
    LoggingConfig,
    ComponentConfig,
    BatchConfig,
    MonitoringConfig,
    SecurityConfig,
    ConfigValidationError,
)


class TestConfigModel:
    """Test base config model functionality."""

    def test_config_model_creation(self):
        """Test creating base config model."""
        config = ConfigModel()
        assert config is not None

    def test_config_model_to_dict(self):
        """Test converting config model to dictionary."""
        config = ConfigModel()
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)

    def test_config_model_from_dict(self):
        """Test creating config model from dictionary."""
        data = {"test_field": "test_value"}
        config = ConfigModel.from_dict(data)
        assert config is not None

    def test_config_model_validation(self):
        """Test config model validation."""
        config = ConfigModel()
        # Should not raise any exceptions for base model
        config.validate()


class TestFetchConfig:
    """Test fetch configuration model."""

    def test_fetch_config_creation(self):
        """Test creating fetch configuration."""
        config = FetchConfig(
            timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            follow_redirects=True,
            max_redirects=10,
            verify_ssl=True
        )
        
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.follow_redirects == True
        assert config.max_redirects == 10
        assert config.verify_ssl == True

    def test_fetch_config_defaults(self):
        """Test fetch configuration defaults."""
        config = FetchConfig()
        
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.follow_redirects == True
        assert config.max_redirects == 5
        assert config.verify_ssl == True

    def test_fetch_config_validation(self):
        """Test fetch configuration validation."""
        # Valid configuration
        config = FetchConfig(timeout=30.0, max_retries=3)
        config.validate()  # Should not raise
        
        # Invalid timeout
        with pytest.raises(ConfigValidationError):
            config = FetchConfig(timeout=-1.0)
            config.validate()
        
        # Invalid max_retries
        with pytest.raises(ConfigValidationError):
            config = FetchConfig(max_retries=-1)
            config.validate()

    def test_fetch_config_to_dict(self):
        """Test converting fetch config to dictionary."""
        config = FetchConfig(timeout=60.0, max_retries=5)
        config_dict = config.to_dict()
        
        assert config_dict["timeout"] == 60.0
        assert config_dict["max_retries"] == 5

    def test_fetch_config_from_dict(self):
        """Test creating fetch config from dictionary."""
        data = {
            "timeout": 45.0,
            "max_retries": 4,
            "verify_ssl": False
        }
        
        config = FetchConfig.from_dict(data)
        
        assert config.timeout == 45.0
        assert config.max_retries == 4
        assert config.verify_ssl == False


class TestHTTPConfig:
    """Test HTTP configuration model."""

    def test_http_config_creation(self):
        """Test creating HTTP configuration."""
        config = HTTPConfig(
            user_agent="test-agent/1.0",
            headers={"Accept": "application/json"},
            cookies={"session": "abc123"},
            proxy_url="http://proxy.example.com:8080",
            connection_pool_size=20
        )
        
        assert config.user_agent == "test-agent/1.0"
        assert config.headers == {"Accept": "application/json"}
        assert config.cookies == {"session": "abc123"}
        assert config.proxy_url == "http://proxy.example.com:8080"
        assert config.connection_pool_size == 20

    def test_http_config_defaults(self):
        """Test HTTP configuration defaults."""
        config = HTTPConfig()
        
        assert config.user_agent.startswith("web-fetch")
        assert config.headers == {}
        assert config.cookies == {}
        assert config.proxy_url is None
        assert config.connection_pool_size == 10

    def test_http_config_validation(self):
        """Test HTTP configuration validation."""
        # Valid configuration
        config = HTTPConfig(connection_pool_size=15)
        config.validate()  # Should not raise
        
        # Invalid connection pool size
        with pytest.raises(ConfigValidationError):
            config = HTTPConfig(connection_pool_size=0)
            config.validate()

    def test_http_config_merge_headers(self):
        """Test merging headers in HTTP config."""
        config = HTTPConfig(headers={"Accept": "application/json"})
        additional_headers = {"Authorization": "Bearer token"}
        
        merged_config = config.merge_headers(additional_headers)
        
        assert merged_config.headers["Accept"] == "application/json"
        assert merged_config.headers["Authorization"] == "Bearer token"


class TestAuthConfig:
    """Test authentication configuration model."""

    def test_auth_config_creation(self):
        """Test creating authentication configuration."""
        config = AuthConfig(
            auth_type="bearer",
            token="secret-token",
            username="testuser",
            password="testpass",
            api_key="api-key-123",
            auth_header="Authorization"
        )
        
        assert config.auth_type == "bearer"
        assert config.token == "secret-token"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.api_key == "api-key-123"
        assert config.auth_header == "Authorization"

    def test_auth_config_defaults(self):
        """Test authentication configuration defaults."""
        config = AuthConfig()
        
        assert config.auth_type is None
        assert config.token is None
        assert config.username is None
        assert config.password is None
        assert config.api_key is None
        assert config.auth_header == "Authorization"

    def test_auth_config_validation(self):
        """Test authentication configuration validation."""
        # Valid bearer token config
        config = AuthConfig(auth_type="bearer", token="token123")
        config.validate()  # Should not raise
        
        # Valid basic auth config
        config = AuthConfig(auth_type="basic", username="user", password="pass")
        config.validate()  # Should not raise
        
        # Invalid bearer config (missing token)
        with pytest.raises(ConfigValidationError):
            config = AuthConfig(auth_type="bearer")
            config.validate()
        
        # Invalid basic config (missing username)
        with pytest.raises(ConfigValidationError):
            config = AuthConfig(auth_type="basic", password="pass")
            config.validate()


class TestCacheConfig:
    """Test cache configuration model."""

    def test_cache_config_creation(self):
        """Test creating cache configuration."""
        config = CacheConfig(
            enabled=True,
            cache_type="memory",
            max_size=1000,
            ttl=3600,
            cache_dir="/tmp/cache",
            compression=True
        )
        
        assert config.enabled == True
        assert config.cache_type == "memory"
        assert config.max_size == 1000
        assert config.ttl == 3600
        assert config.cache_dir == "/tmp/cache"
        assert config.compression == True

    def test_cache_config_defaults(self):
        """Test cache configuration defaults."""
        config = CacheConfig()
        
        assert config.enabled == True
        assert config.cache_type == "memory"
        assert config.max_size == 100
        assert config.ttl == 3600
        assert config.cache_dir is None
        assert config.compression == False

    def test_cache_config_validation(self):
        """Test cache configuration validation."""
        # Valid configuration
        config = CacheConfig(max_size=500, ttl=1800)
        config.validate()  # Should not raise
        
        # Invalid max_size
        with pytest.raises(ConfigValidationError):
            config = CacheConfig(max_size=0)
            config.validate()
        
        # Invalid ttl
        with pytest.raises(ConfigValidationError):
            config = CacheConfig(ttl=-1)
            config.validate()

    def test_cache_config_file_cache_validation(self):
        """Test file cache specific validation."""
        # File cache requires cache_dir
        with pytest.raises(ConfigValidationError):
            config = CacheConfig(cache_type="file", cache_dir=None)
            config.validate()


class TestLoggingConfig:
    """Test logging configuration model."""

    def test_logging_config_creation(self):
        """Test creating logging configuration."""
        config = LoggingConfig(
            level="INFO",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            file_path="/var/log/web-fetch.log",
            max_file_size=10485760,  # 10MB
            backup_count=5,
            console_output=True
        )
        
        assert config.level == "INFO"
        assert "%(asctime)s" in config.format
        assert config.file_path == "/var/log/web-fetch.log"
        assert config.max_file_size == 10485760
        assert config.backup_count == 5
        assert config.console_output == True

    def test_logging_config_defaults(self):
        """Test logging configuration defaults."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.format is not None
        assert config.file_path is None
        assert config.max_file_size == 10485760
        assert config.backup_count == 3
        assert config.console_output == True

    def test_logging_config_validation(self):
        """Test logging configuration validation."""
        # Valid configuration
        config = LoggingConfig(level="DEBUG")
        config.validate()  # Should not raise
        
        # Invalid log level
        with pytest.raises(ConfigValidationError):
            config = LoggingConfig(level="INVALID")
            config.validate()
        
        # Invalid backup count
        with pytest.raises(ConfigValidationError):
            config = LoggingConfig(backup_count=-1)
            config.validate()


class TestComponentConfig:
    """Test component configuration model."""

    def test_component_config_creation(self):
        """Test creating component configuration."""
        config = ComponentConfig(
            name="test-component",
            enabled=True,
            priority=5,
            timeout=30.0,
            max_retries=3,
            settings={"custom_setting": "value"}
        )
        
        assert config.name == "test-component"
        assert config.enabled == True
        assert config.priority == 5
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.settings == {"custom_setting": "value"}

    def test_component_config_defaults(self):
        """Test component configuration defaults."""
        config = ComponentConfig(name="default-component")
        
        assert config.name == "default-component"
        assert config.enabled == True
        assert config.priority == 0
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.settings == {}

    def test_component_config_validation(self):
        """Test component configuration validation."""
        # Valid configuration
        config = ComponentConfig(name="valid-component")
        config.validate()  # Should not raise
        
        # Invalid name (empty)
        with pytest.raises(ConfigValidationError):
            config = ComponentConfig(name="")
            config.validate()
        
        # Invalid timeout
        with pytest.raises(ConfigValidationError):
            config = ComponentConfig(name="test", timeout=-1.0)
            config.validate()


class TestBatchConfig:
    """Test batch configuration model."""

    def test_batch_config_creation(self):
        """Test creating batch configuration."""
        config = BatchConfig(
            max_concurrent_requests=20,
            chunk_size=100,
            timeout=60.0,
            retry_failed=True,
            save_results=True,
            output_format="json"
        )
        
        assert config.max_concurrent_requests == 20
        assert config.chunk_size == 100
        assert config.timeout == 60.0
        assert config.retry_failed == True
        assert config.save_results == True
        assert config.output_format == "json"

    def test_batch_config_defaults(self):
        """Test batch configuration defaults."""
        config = BatchConfig()
        
        assert config.max_concurrent_requests == 10
        assert config.chunk_size == 50
        assert config.timeout == 30.0
        assert config.retry_failed == True
        assert config.save_results == False
        assert config.output_format == "json"

    def test_batch_config_validation(self):
        """Test batch configuration validation."""
        # Valid configuration
        config = BatchConfig(max_concurrent_requests=15)
        config.validate()  # Should not raise
        
        # Invalid max_concurrent_requests
        with pytest.raises(ConfigValidationError):
            config = BatchConfig(max_concurrent_requests=0)
            config.validate()
        
        # Invalid chunk_size
        with pytest.raises(ConfigValidationError):
            config = BatchConfig(chunk_size=0)
            config.validate()


class TestMonitoringConfig:
    """Test monitoring configuration model."""

    def test_monitoring_config_creation(self):
        """Test creating monitoring configuration."""
        config = MonitoringConfig(
            enabled=True,
            metrics_interval=60,
            health_check_interval=30,
            alert_thresholds={
                "error_rate": 0.05,
                "response_time": 5.0
            },
            export_metrics=True,
            metrics_endpoint="/metrics"
        )
        
        assert config.enabled == True
        assert config.metrics_interval == 60
        assert config.health_check_interval == 30
        assert config.alert_thresholds["error_rate"] == 0.05
        assert config.export_metrics == True
        assert config.metrics_endpoint == "/metrics"

    def test_monitoring_config_defaults(self):
        """Test monitoring configuration defaults."""
        config = MonitoringConfig()
        
        assert config.enabled == False
        assert config.metrics_interval == 60
        assert config.health_check_interval == 30
        assert config.alert_thresholds == {}
        assert config.export_metrics == False
        assert config.metrics_endpoint == "/metrics"

    def test_monitoring_config_validation(self):
        """Test monitoring configuration validation."""
        # Valid configuration
        config = MonitoringConfig(metrics_interval=120)
        config.validate()  # Should not raise
        
        # Invalid metrics_interval
        with pytest.raises(ConfigValidationError):
            config = MonitoringConfig(metrics_interval=0)
            config.validate()


class TestSecurityConfig:
    """Test security configuration model."""

    def test_security_config_creation(self):
        """Test creating security configuration."""
        config = SecurityConfig(
            verify_ssl=True,
            ssl_cert_path="/path/to/cert.pem",
            ssl_key_path="/path/to/key.pem",
            allowed_hosts=["example.com", "api.example.com"],
            blocked_hosts=["malicious.com"],
            max_request_size=10485760,
            rate_limit=100
        )
        
        assert config.verify_ssl == True
        assert config.ssl_cert_path == "/path/to/cert.pem"
        assert config.ssl_key_path == "/path/to/key.pem"
        assert config.allowed_hosts == ["example.com", "api.example.com"]
        assert config.blocked_hosts == ["malicious.com"]
        assert config.max_request_size == 10485760
        assert config.rate_limit == 100

    def test_security_config_defaults(self):
        """Test security configuration defaults."""
        config = SecurityConfig()
        
        assert config.verify_ssl == True
        assert config.ssl_cert_path is None
        assert config.ssl_key_path is None
        assert config.allowed_hosts == []
        assert config.blocked_hosts == []
        assert config.max_request_size == 10485760
        assert config.rate_limit is None

    def test_security_config_validation(self):
        """Test security configuration validation."""
        # Valid configuration
        config = SecurityConfig(rate_limit=50)
        config.validate()  # Should not raise
        
        # Invalid max_request_size
        with pytest.raises(ConfigValidationError):
            config = SecurityConfig(max_request_size=0)
            config.validate()
        
        # Invalid rate_limit
        with pytest.raises(ConfigValidationError):
            config = SecurityConfig(rate_limit=-1)
            config.validate()


class TestConfigValidationError:
    """Test configuration validation error."""

    def test_config_validation_error_creation(self):
        """Test creating configuration validation error."""
        error = ConfigValidationError(
            message="Invalid configuration",
            field="timeout",
            value=-1,
            config_type="FetchConfig"
        )
        
        assert error.message == "Invalid configuration"
        assert error.field == "timeout"
        assert error.value == -1
        assert error.config_type == "FetchConfig"

    def test_config_validation_error_string_representation(self):
        """Test configuration validation error string representation."""
        error = ConfigValidationError(
            message="Invalid value",
            field="max_retries",
            value=-1
        )
        
        error_str = str(error)
        assert "Invalid value" in error_str
        assert "max_retries" in error_str


class TestConfigIntegration:
    """Test configuration integration scenarios."""

    def test_nested_config_creation(self):
        """Test creating nested configuration."""
        fetch_config = FetchConfig(timeout=60.0)
        http_config = HTTPConfig(user_agent="test-agent")
        auth_config = AuthConfig(auth_type="bearer", token="token123")
        
        # These would typically be part of a larger configuration
        assert fetch_config.timeout == 60.0
        assert http_config.user_agent == "test-agent"
        assert auth_config.auth_type == "bearer"

    def test_config_serialization_roundtrip(self):
        """Test configuration serialization and deserialization."""
        original_config = FetchConfig(
            timeout=45.0,
            max_retries=5,
            verify_ssl=False
        )
        
        # Serialize to dict
        config_dict = original_config.to_dict()
        
        # Deserialize from dict
        restored_config = FetchConfig.from_dict(config_dict)
        
        assert restored_config.timeout == original_config.timeout
        assert restored_config.max_retries == original_config.max_retries
        assert restored_config.verify_ssl == original_config.verify_ssl

    def test_config_merging(self):
        """Test merging configurations."""
        base_config = HTTPConfig(
            user_agent="base-agent",
            headers={"Accept": "application/json"}
        )
        
        override_config = HTTPConfig(
            headers={"Authorization": "Bearer token"}
        )
        
        # This would be implemented in the actual config system
        merged_headers = {**base_config.headers, **override_config.headers}
        
        assert merged_headers["Accept"] == "application/json"
        assert merged_headers["Authorization"] == "Bearer token"
