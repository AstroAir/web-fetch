"""
Comprehensive tests for the config loader module.
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from web_fetch.config.loader import (
    ConfigLoader,
    ConfigFormat,
    ConfigSource,
    ConfigLoadError,
    EnvironmentConfigLoader,
    FileConfigLoader,
    RemoteConfigLoader,
)


class TestConfigFormat:
    """Test configuration format detection and handling."""
    
    def test_format_detection_from_extension(self):
        """Test format detection from file extension."""
        assert ConfigFormat.from_extension(".json") == ConfigFormat.JSON
        assert ConfigFormat.from_extension(".yaml") == ConfigFormat.YAML
        assert ConfigFormat.from_extension(".yml") == ConfigFormat.YAML
        assert ConfigFormat.from_extension(".toml") == ConfigFormat.TOML
        assert ConfigFormat.from_extension(".ini") == ConfigFormat.INI
    
    def test_format_detection_unknown_extension(self):
        """Test format detection for unknown extensions."""
        assert ConfigFormat.from_extension(".unknown") == ConfigFormat.JSON  # Default
        assert ConfigFormat.from_extension("") == ConfigFormat.JSON  # Default
    
    def test_format_mime_types(self):
        """Test format MIME type mapping."""
        assert ConfigFormat.JSON.mime_type == "application/json"
        assert ConfigFormat.YAML.mime_type == "application/x-yaml"
        assert ConfigFormat.TOML.mime_type == "application/toml"
        assert ConfigFormat.INI.mime_type == "text/plain"


class TestConfigSource:
    """Test configuration source model."""
    
    def test_source_creation(self):
        """Test configuration source creation."""
        source = ConfigSource(
            name="app_config",
            path="/etc/app/config.json",
            format=ConfigFormat.JSON,
            priority=1,
            required=True
        )
        
        assert source.name == "app_config"
        assert source.path == "/etc/app/config.json"
        assert source.format == ConfigFormat.JSON
        assert source.priority == 1
        assert source.required is True
    
    def test_source_from_path(self):
        """Test creating source from file path."""
        source = ConfigSource.from_path("/config/settings.yaml")
        
        assert source.path == "/config/settings.yaml"
        assert source.format == ConfigFormat.YAML
        assert source.name == "settings"
    
    def test_source_comparison(self):
        """Test source comparison by priority."""
        source1 = ConfigSource("config1", "/path1", ConfigFormat.JSON, priority=1)
        source2 = ConfigSource("config2", "/path2", ConfigFormat.JSON, priority=2)
        source3 = ConfigSource("config3", "/path3", ConfigFormat.JSON, priority=1)
        
        assert source1 < source2  # Lower priority number = higher priority
        assert source1 == source3  # Same priority
        assert source2 > source1


class TestFileConfigLoader:
    """Test file-based configuration loader."""
    
    @pytest.fixture
    def loader(self):
        """Create file config loader."""
        return FileConfigLoader()
    
    def test_load_json_config(self, loader):
        """Test loading JSON configuration."""
        json_content = {
            "app_name": "test_app",
            "debug": True,
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(json_content))):
            config = loader.load_file("/config/app.json", ConfigFormat.JSON)
            
            assert config["app_name"] == "test_app"
            assert config["debug"] is True
            assert config["database"]["host"] == "localhost"
            assert config["database"]["port"] == 5432
    
    def test_load_yaml_config(self, loader):
        """Test loading YAML configuration."""
        yaml_content = """
        app_name: test_app
        debug: true
        database:
          host: localhost
          port: 5432
        features:
          - feature1
          - feature2
        """
        
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            with patch("yaml.safe_load") as mock_yaml:
                mock_yaml.return_value = {
                    "app_name": "test_app",
                    "debug": True,
                    "database": {"host": "localhost", "port": 5432},
                    "features": ["feature1", "feature2"]
                }
                
                config = loader.load_file("/config/app.yaml", ConfigFormat.YAML)
                
                assert config["app_name"] == "test_app"
                assert config["features"] == ["feature1", "feature2"]
    
    def test_load_toml_config(self, loader):
        """Test loading TOML configuration."""
        toml_content = """
        app_name = "test_app"
        debug = true
        
        [database]
        host = "localhost"
        port = 5432
        """
        
        with patch("builtins.open", mock_open(read_data=toml_content)):
            with patch("toml.load") as mock_toml:
                mock_toml.return_value = {
                    "app_name": "test_app",
                    "debug": True,
                    "database": {"host": "localhost", "port": 5432}
                }
                
                config = loader.load_file("/config/app.toml", ConfigFormat.TOML)
                
                assert config["app_name"] == "test_app"
                assert config["database"]["host"] == "localhost"
    
    def test_load_ini_config(self, loader):
        """Test loading INI configuration."""
        ini_content = """
        [DEFAULT]
        app_name = test_app
        debug = true
        
        [database]
        host = localhost
        port = 5432
        """
        
        with patch("builtins.open", mock_open(read_data=ini_content)):
            with patch("configparser.ConfigParser") as mock_parser:
                mock_config = mock_parser.return_value
                mock_config.read_string.return_value = None
                mock_config.sections.return_value = ["database"]
                mock_config.__getitem__.side_effect = lambda section: {
                    "DEFAULT": {"app_name": "test_app", "debug": "true"},
                    "database": {"host": "localhost", "port": "5432"}
                }[section]
                
                config = loader.load_file("/config/app.ini", ConfigFormat.INI)
                
                # INI loader should convert to nested structure
                assert "DEFAULT" in config
                assert "database" in config
    
    def test_load_nonexistent_file(self, loader):
        """Test loading non-existent file."""
        with pytest.raises(ConfigLoadError, match="File not found"):
            loader.load_file("/nonexistent/config.json", ConfigFormat.JSON)
    
    def test_load_invalid_json(self, loader):
        """Test loading invalid JSON file."""
        invalid_json = '{"invalid": json, "missing": quote}'
        
        with patch("builtins.open", mock_open(read_data=invalid_json)):
            with pytest.raises(ConfigLoadError, match="Invalid JSON"):
                loader.load_file("/config/invalid.json", ConfigFormat.JSON)
    
    def test_load_with_encoding(self, loader):
        """Test loading file with specific encoding."""
        json_content = {"message": "héllo wörld"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(json_content))):
            config = loader.load_file(
                "/config/unicode.json", 
                ConfigFormat.JSON, 
                encoding="utf-8"
            )
            
            assert config["message"] == "héllo wörld"


class TestEnvironmentConfigLoader:
    """Test environment-based configuration loader."""
    
    @pytest.fixture
    def loader(self):
        """Create environment config loader."""
        return EnvironmentConfigLoader()
    
    def test_load_environment_variables(self, loader):
        """Test loading configuration from environment variables."""
        env_vars = {
            "APP_NAME": "test_app",
            "APP_DEBUG": "true",
            "APP_DATABASE_HOST": "localhost",
            "APP_DATABASE_PORT": "5432",
            "OTHER_VAR": "ignored"
        }
        
        with patch.dict("os.environ", env_vars):
            config = loader.load_environment(prefix="APP_")
            
            assert config["NAME"] == "test_app"
            assert config["DEBUG"] == "true"
            assert config["DATABASE_HOST"] == "localhost"
            assert config["DATABASE_PORT"] == "5432"
            assert "OTHER_VAR" not in config
    
    def test_load_with_type_conversion(self, loader):
        """Test loading with automatic type conversion."""
        env_vars = {
            "APP_DEBUG": "true",
            "APP_PORT": "8080",
            "APP_TIMEOUT": "30.5",
            "APP_FEATURES": "feature1,feature2,feature3"
        }
        
        with patch.dict("os.environ", env_vars):
            config = loader.load_environment(
                prefix="APP_",
                convert_types=True,
                list_separator=","
            )
            
            assert config["DEBUG"] is True
            assert config["PORT"] == 8080
            assert config["TIMEOUT"] == 30.5
            assert config["FEATURES"] == ["feature1", "feature2", "feature3"]
    
    def test_load_nested_structure(self, loader):
        """Test loading nested configuration structure."""
        env_vars = {
            "APP_DATABASE__HOST": "localhost",
            "APP_DATABASE__PORT": "5432",
            "APP_CACHE__REDIS__HOST": "redis-server",
            "APP_CACHE__REDIS__PORT": "6379"
        }
        
        with patch.dict("os.environ", env_vars):
            config = loader.load_environment(
                prefix="APP_",
                nested_separator="__"
            )
            
            assert config["DATABASE"]["HOST"] == "localhost"
            assert config["DATABASE"]["PORT"] == "5432"
            assert config["CACHE"]["REDIS"]["HOST"] == "redis-server"
            assert config["CACHE"]["REDIS"]["PORT"] == "6379"


class TestRemoteConfigLoader:
    """Test remote configuration loader."""
    
    @pytest.fixture
    def loader(self):
        """Create remote config loader."""
        return RemoteConfigLoader()
    
    @pytest.mark.asyncio
    async def test_load_remote_json_config(self, loader):
        """Test loading JSON configuration from remote URL."""
        config_data = {
            "app_name": "remote_app",
            "version": "1.0.0",
            "features": ["remote_feature"]
        }
        
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = mock_get.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = config_data
            
            config = await loader.load_remote(
                "https://config.example.com/app.json",
                ConfigFormat.JSON
            )
            
            assert config["app_name"] == "remote_app"
            assert config["version"] == "1.0.0"
            assert config["features"] == ["remote_feature"]
    
    @pytest.mark.asyncio
    async def test_load_remote_with_authentication(self, loader):
        """Test loading remote configuration with authentication."""
        config_data = {"secure": "config"}
        
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = mock_get.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = config_data
            
            config = await loader.load_remote(
                "https://secure.example.com/config.json",
                ConfigFormat.JSON,
                headers={"Authorization": "Bearer token123"}
            )
            
            assert config["secure"] == "config"
            
            # Verify authentication header was sent
            call_args = mock_get.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer token123"
    
    @pytest.mark.asyncio
    async def test_load_remote_config_error(self, loader):
        """Test handling remote configuration load errors."""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = mock_get.return_value.__aenter__.return_value
            mock_response.status = 404
            mock_response.raise_for_status.side_effect = Exception("Not Found")
            
            with pytest.raises(ConfigLoadError, match="Failed to load remote config"):
                await loader.load_remote(
                    "https://config.example.com/missing.json",
                    ConfigFormat.JSON
                )


class TestConfigLoader:
    """Test main configuration loader."""
    
    @pytest.fixture
    def loader(self):
        """Create main config loader."""
        return ConfigLoader()
    
    def test_add_config_sources(self, loader):
        """Test adding configuration sources."""
        source1 = ConfigSource("config1", "/path1.json", ConfigFormat.JSON, priority=1)
        source2 = ConfigSource("config2", "/path2.yaml", ConfigFormat.YAML, priority=2)
        
        loader.add_source(source1)
        loader.add_source(source2)
        
        assert len(loader.sources) == 2
        # Sources should be sorted by priority
        assert loader.sources[0].priority == 1
        assert loader.sources[1].priority == 2
    
    def test_load_multiple_sources(self, loader):
        """Test loading configuration from multiple sources."""
        # Base configuration
        base_config = {
            "app_name": "test_app",
            "debug": False,
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        # Override configuration
        override_config = {
            "debug": True,
            "database": {
                "host": "production-db"
            },
            "new_feature": True
        }
        
        source1 = ConfigSource("base", "/base.json", ConfigFormat.JSON, priority=2)
        source2 = ConfigSource("override", "/override.json", ConfigFormat.JSON, priority=1)
        
        loader.add_source(source1)
        loader.add_source(source2)
        
        with patch.object(loader.file_loader, "load_file") as mock_load:
            mock_load.side_effect = [override_config, base_config]
            
            config = loader.load()
            
            # Higher priority (lower number) should override
            assert config["app_name"] == "test_app"  # From base
            assert config["debug"] is True  # Overridden
            assert config["database"]["host"] == "production-db"  # Overridden
            assert config["database"]["port"] == 5432  # From base
            assert config["new_feature"] is True  # From override
    
    def test_load_with_environment_override(self, loader):
        """Test loading with environment variable overrides."""
        file_config = {
            "app_name": "file_app",
            "debug": False,
            "port": 8000
        }
        
        env_vars = {
            "APP_DEBUG": "true",
            "APP_PORT": "9000"
        }
        
        source = ConfigSource("file", "/config.json", ConfigFormat.JSON)
        loader.add_source(source)
        loader.enable_environment_override(prefix="APP_")
        
        with patch.object(loader.file_loader, "load_file", return_value=file_config):
            with patch.dict("os.environ", env_vars):
                config = loader.load()
                
                assert config["app_name"] == "file_app"  # From file
                assert config["debug"] == "true"  # From environment
                assert config["port"] == "9000"  # From environment
    
    def test_load_required_source_missing(self, loader):
        """Test loading when required source is missing."""
        source = ConfigSource(
            "required", 
            "/missing.json", 
            ConfigFormat.JSON, 
            required=True
        )
        loader.add_source(source)
        
        with patch.object(loader.file_loader, "load_file") as mock_load:
            mock_load.side_effect = ConfigLoadError("File not found")
            
            with pytest.raises(ConfigLoadError, match="Required configuration source"):
                loader.load()
    
    def test_load_optional_source_missing(self, loader):
        """Test loading when optional source is missing."""
        required_source = ConfigSource(
            "required", 
            "/config.json", 
            ConfigFormat.JSON, 
            required=True
        )
        optional_source = ConfigSource(
            "optional", 
            "/optional.json", 
            ConfigFormat.JSON, 
            required=False
        )
        
        loader.add_source(required_source)
        loader.add_source(optional_source)
        
        required_config = {"app_name": "test_app"}
        
        with patch.object(loader.file_loader, "load_file") as mock_load:
            def side_effect(path, format):
                if "optional" in path:
                    raise ConfigLoadError("File not found")
                return required_config
            
            mock_load.side_effect = side_effect
            
            # Should succeed despite missing optional source
            config = loader.load()
            assert config["app_name"] == "test_app"
    
    def test_config_validation(self, loader):
        """Test configuration validation."""
        def validate_config(config):
            if "app_name" not in config:
                raise ValueError("app_name is required")
            if not isinstance(config.get("port"), int):
                raise ValueError("port must be an integer")
        
        loader.add_validator(validate_config)
        
        source = ConfigSource("config", "/config.json", ConfigFormat.JSON)
        loader.add_source(source)
        
        # Valid configuration
        valid_config = {"app_name": "test_app", "port": 8000}
        with patch.object(loader.file_loader, "load_file", return_value=valid_config):
            config = loader.load()
            assert config["app_name"] == "test_app"
        
        # Invalid configuration
        invalid_config = {"port": "not_an_integer"}
        with patch.object(loader.file_loader, "load_file", return_value=invalid_config):
            with pytest.raises(ConfigLoadError, match="Configuration validation failed"):
                loader.load()
    
    def test_config_caching(self, loader):
        """Test configuration caching."""
        source = ConfigSource("config", "/config.json", ConfigFormat.JSON)
        loader.add_source(source)
        loader.enable_caching(ttl=60)
        
        config_data = {"app_name": "cached_app"}
        
        with patch.object(loader.file_loader, "load_file", return_value=config_data) as mock_load:
            # First load
            config1 = loader.load()
            assert config1["app_name"] == "cached_app"
            
            # Second load should use cache
            config2 = loader.load()
            assert config2["app_name"] == "cached_app"
            
            # File should only be loaded once due to caching
            assert mock_load.call_count == 1
    
    def test_config_reload(self, loader):
        """Test configuration reloading."""
        source = ConfigSource("config", "/config.json", ConfigFormat.JSON)
        loader.add_source(source)
        
        original_config = {"version": "1.0"}
        updated_config = {"version": "2.0"}
        
        with patch.object(loader.file_loader, "load_file") as mock_load:
            mock_load.side_effect = [original_config, updated_config]
            
            # Initial load
            config1 = loader.load()
            assert config1["version"] == "1.0"
            
            # Reload
            config2 = loader.reload()
            assert config2["version"] == "2.0"
            
            assert mock_load.call_count == 2
