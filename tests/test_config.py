"""
Comprehensive tests for the configuration module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from web_fetch.config import (
    ConfigManager,
    config_manager,
    GlobalConfig,
    LoggingConfig,
    SecurityConfig,
    PerformanceConfig,
    FeatureFlags,
    EnvironmentConfig,
    ConfigLoader,
    ConfigValidator,
)
from web_fetch.config.models import Environment, LogLevel


class TestGlobalConfig:
    """Test global configuration model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GlobalConfig()

        assert config.environment.environment == Environment.DEVELOPMENT
        assert config.environment.debug is False  # Default is False
        assert config.logging.level == LogLevel.INFO
        assert config.security.verify_ssl is True
        assert config.performance.max_concurrent_requests == 50  # Check actual default

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = GlobalConfig(
            environment=EnvironmentConfig(environment=Environment.PRODUCTION, debug=False)
        )
        assert config.environment.environment == Environment.PRODUCTION
        assert config.environment.debug is False

    def test_nested_config_updates(self):
        """Test updating nested configuration."""
        config = GlobalConfig()
        
        # Update logging config
        config.logging.level = LogLevel.DEBUG
        config.logging.enable_file = True

        assert config.logging.level == LogLevel.DEBUG
        assert config.logging.enable_file is True

    def test_feature_flags(self):
        """Test feature flags configuration."""
        config = GlobalConfig()
        
        # Test default feature flags
        assert config.features.enable_caching is True
        assert config.features.enable_rate_limiting is True
        assert config.features.enable_metrics is True
        
        # Update feature flags
        config.features.enable_caching = False
        config.features.enable_js_rendering = True

        assert config.features.enable_caching is False
        assert config.features.enable_js_rendering is True


class TestConfigLoader:
    """Test configuration loader."""

    def test_load_from_dict(self):
        """Test loading configuration from dictionary."""
        loader = ConfigLoader()
        
        config_dict = {
            "environment": "production",
            "debug": False,
            "logging": {
                "level": "warning",
                "enable_file_logging": True
            },
            "security": {
                "verify_ssl": True,
                "max_redirects": 5
            }
        }
        
        config = loader.load_from_dict(config_dict)

        assert config.environment.environment == Environment.PRODUCTION
        assert config.environment.debug is False
        assert config.logging.level == LogLevel.WARNING
        assert config.logging.enable_file is True
        assert config.security.verify_ssl is True
        assert config.security.max_redirects == 5

    def test_load_from_env(self):
        """Test loading configuration from environment variables."""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {
            'WEB_FETCH_ENVIRONMENT': 'production',
            'WEB_FETCH_DEBUG': 'false',
            'WEB_FETCH_LOG_LEVEL': 'error',
            'WEB_FETCH_VERIFY_SSL': 'false',
            'WEB_FETCH_MAX_CONNECTIONS': '20'
        }):
            config = loader.load_from_env()
            
            assert config.environment.environment == Environment.PRODUCTION
            assert config.environment.debug is False
            assert config.logging.level == LogLevel.ERROR
            assert config.security.verify_ssl is False
            assert config.performance.max_connections == 20

    def test_load_from_file_json(self):
        """Test loading configuration from JSON file."""
        loader = ConfigLoader()
        
        config_content = '''
        {
            "environment": "staging",
            "debug": true,
            "logging": {
                "level": "debug",
                "log_file": "/tmp/web_fetch.log"
            }
        }
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            try:
                config = loader.load_from_file(f.name)
                
                assert config.environment.environment == Environment.STAGING
                assert config.environment.debug is True
                assert config.logging.level == LogLevel.DEBUG
                assert str(config.logging.file_path) == "/tmp/web_fetch.log"
            finally:
                os.unlink(f.name)

    @pytest.mark.skipif(not hasattr(ConfigLoader, '_has_yaml') or not ConfigLoader._has_yaml, 
                       reason="PyYAML not available")
    def test_load_from_file_yaml(self):
        """Test loading configuration from YAML file."""
        loader = ConfigLoader()
        
        config_content = '''
        environment: staging
        debug: true
        logging:
          level: debug
          log_file: /tmp/web_fetch.log
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            try:
                config = loader.load_from_file(f.name)
                
                assert config.environment == Environment.STAGING
                assert config.debug is True
                assert config.logging.level == LogLevel.DEBUG
                assert config.logging.log_file == "/tmp/web_fetch.log"
            finally:
                os.unlink(f.name)

    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file."""
        loader = ConfigLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load_from_file("/nonexistent/config.json")

    def test_load_from_invalid_json(self):
        """Test loading from invalid JSON file."""
        loader = ConfigLoader()
        
        invalid_content = '{"environment": "production", "debug": true'  # Missing closing brace
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(invalid_content)
            f.flush()
            
            try:
                with pytest.raises(ValueError):
                    loader.load_from_file(f.name)
            finally:
                os.unlink(f.name)


class TestConfigValidator:
    """Test configuration validator."""

    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        validator = ConfigValidator()
        config = GlobalConfig()
        
        is_valid, errors, warnings = validator.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_timeout(self):
        """Test validation of invalid timeout values."""
        validator = ConfigValidator()
        config = GlobalConfig()
        
        # Set invalid timeout
        config.performance.connection_timeout = -1.0
        
        is_valid, errors, warnings = validator.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("timeout" in error.lower() for error in errors)

    def test_validate_invalid_max_requests(self):
        """Test validation of invalid max requests."""
        validator = ConfigValidator()
        config = GlobalConfig()
        
        # Set invalid max requests
        config.performance.max_concurrent_requests = 0
        
        is_valid, errors, warnings = validator.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("concurrent" in error.lower() for error in errors)

    def test_validate_invalid_log_file_path(self):
        """Test validation of invalid log file path."""
        validator = ConfigValidator()
        config = GlobalConfig()
        
        # Set invalid log file path
        from pathlib import Path
        config.logging.file_path = Path("/invalid/path/that/does/not/exist/log.txt")
        config.logging.enable_file = True
        
        is_valid, errors, warnings = validator.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0


class TestConfigManager:
    """Test configuration manager."""

    def test_config_manager_singleton(self):
        """Test that config manager is a singleton."""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        
        assert manager1 is manager2

    def test_load_config_from_dict(self):
        """Test loading configuration from dictionary."""
        manager = ConfigManager()
        
        config_dict = {
            "environment": "production",
            "debug": False,
            "logging": {
                "level": "warning"
            }
        }
        
        manager.load_from_dict(config_dict)
        config = manager.get_config()
        
        assert config.environment.environment == Environment.PRODUCTION
        assert config.environment.debug is False
        assert config.logging.level == LogLevel.WARNING

    def test_update_config(self):
        """Test updating configuration."""
        manager = ConfigManager()
        
        # Initial config
        manager.load_from_dict({"debug": True})
        assert manager.get_config().environment.debug is True
        
        # Update config
        updates = {"debug": False, "logging": {"level": "error"}}
        manager.update_config(updates)
        
        config = manager.get_config()
        assert config.environment.debug is False
        assert config.logging.level == LogLevel.ERROR

    def test_get_nested_value(self):
        """Test getting nested configuration values."""
        manager = ConfigManager()
        
        config_dict = {
            "logging": {
                "level": "debug",
                "enable_file_logging": True
            }
        }
        
        manager.load_from_dict(config_dict)
        
        assert manager.get("logging.level") == LogLevel.DEBUG
        assert manager.get("logging.enable_file") is True
        assert manager.get("nonexistent.key", "default") == "default"

    def test_set_nested_value(self):
        """Test setting nested configuration values."""
        manager = ConfigManager()

        # Load default configuration first
        manager.load_from_dict({})

        manager.set("logging.level", "warning")
        manager.set("security.verify_ssl", False)
        
        config = manager.get_config()
        assert config.logging.level == LogLevel.WARNING
        assert config.security.verify_ssl is False

    def test_config_validation_on_load(self):
        """Test that configuration is validated when loaded."""
        manager = ConfigManager()
        
        # Invalid config
        invalid_config = {
            "performance": {
                "max_concurrent_requests": -1  # Invalid negative value
            }
        }
        
        with pytest.raises(Exception):  # Could be ValidationError or ValueError
            manager.load_from_dict(invalid_config)

    def test_global_config_manager(self):
        """Test the global config manager instance."""
        # Test that the global instance works
        config_manager.load_from_dict({"debug": True})
        assert config_manager.get_config().environment.debug is True
        
        # Reset for other tests
        config_manager.load_from_dict({})


class TestEnvironmentConfig:
    """Test environment-specific configuration."""

    def test_development_environment(self):
        """Test development environment configuration."""
        config = EnvironmentConfig.for_environment(Environment.DEVELOPMENT)
        
        assert config.environment.debug is True
        assert config.logging.level == LogLevel.DEBUG

    def test_production_environment(self):
        """Test production environment configuration."""
        config = EnvironmentConfig.for_environment(Environment.PRODUCTION)
        
        assert config.environment.debug is False
        assert config.logging.level == LogLevel.WARNING
        assert config.security.verify_ssl is True

    def test_testing_environment(self):
        """Test testing environment configuration."""
        config = EnvironmentConfig.for_environment(Environment.TESTING)
        
        assert config.environment.debug is True
        assert config.logging.level == LogLevel.DEBUG
        # Testing might have different security settings
