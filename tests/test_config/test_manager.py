"""
Comprehensive tests for the config manager module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from web_fetch.config.manager import (
    ConfigManager,
    ConfigChangeEvent,
    ConfigWatcher,
    ConfigCache,
    ConfigError,
    ConfigValidationError,
)
from web_fetch.config.loader import ConfigLoader, ConfigSource, ConfigFormat


class TestConfigChangeEvent:
    """Test configuration change event model."""
    
    def test_event_creation(self):
        """Test configuration change event creation."""
        event = ConfigChangeEvent(
            source="config.json",
            change_type="updated",
            old_value={"debug": False},
            new_value={"debug": True},
            path="debug"
        )
        
        assert event.source == "config.json"
        assert event.change_type == "updated"
        assert event.old_value == {"debug": False}
        assert event.new_value == {"debug": True}
        assert event.path == "debug"
        assert event.timestamp is not None
    
    def test_event_serialization(self):
        """Test configuration change event serialization."""
        event = ConfigChangeEvent(
            source="app.yaml",
            change_type="added",
            new_value={"new_feature": True},
            path="new_feature"
        )
        
        data = event.to_dict()
        
        assert data["source"] == "app.yaml"
        assert data["change_type"] == "added"
        assert data["new_value"] == {"new_feature": True}
        assert data["path"] == "new_feature"
        assert "timestamp" in data


class TestConfigCache:
    """Test configuration cache functionality."""
    
    @pytest.fixture
    def cache(self):
        """Create configuration cache."""
        return ConfigCache(ttl=60, max_size=100)
    
    def test_cache_initialization(self, cache):
        """Test cache initialization."""
        assert cache.ttl == 60
        assert cache.max_size == 100
        assert len(cache._cache) == 0
    
    def test_cache_set_and_get(self, cache):
        """Test setting and getting cache values."""
        config_data = {"app_name": "test_app", "debug": True}
        
        cache.set("test_key", config_data)
        
        retrieved = cache.get("test_key")
        assert retrieved == config_data
    
    def test_cache_expiration(self, cache):
        """Test cache expiration."""
        cache.ttl = 0.1  # Very short TTL for testing
        
        config_data = {"temp": "data"}
        cache.set("temp_key", config_data)
        
        # Should be available immediately
        assert cache.get("temp_key") == config_data
        
        # Wait for expiration
        import time
        time.sleep(0.2)
        
        # Should be expired
        assert cache.get("temp_key") is None
    
    def test_cache_max_size(self, cache):
        """Test cache maximum size limit."""
        cache.max_size = 3
        
        # Fill cache to capacity
        for i in range(3):
            cache.set(f"key_{i}", {"value": i})
        
        # All items should be present
        for i in range(3):
            assert cache.get(f"key_{i}") == {"value": i}
        
        # Add one more item (should evict oldest)
        cache.set("key_3", {"value": 3})
        
        # First item should be evicted
        assert cache.get("key_0") is None
        assert cache.get("key_3") == {"value": 3}
    
    def test_cache_clear(self, cache):
        """Test clearing cache."""
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})
        
        assert len(cache._cache) == 2
        
        cache.clear()
        
        assert len(cache._cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Generate some cache activity
        cache.set("key1", {"data": 1})
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5


class TestConfigWatcher:
    """Test configuration file watcher."""
    
    @pytest.fixture
    def watcher(self):
        """Create configuration watcher."""
        return ConfigWatcher()
    
    def test_watcher_initialization(self, watcher):
        """Test watcher initialization."""
        assert len(watcher._watched_files) == 0
        assert len(watcher._callbacks) == 0
        assert watcher._observer is None
    
    def test_add_watch_file(self, watcher):
        """Test adding file to watch."""
        callback = MagicMock()
        
        watcher.add_watch("/config/app.json", callback)
        
        assert "/config/app.json" in watcher._watched_files
        assert callback in watcher._callbacks["/config/app.json"]
    
    def test_remove_watch_file(self, watcher):
        """Test removing file from watch."""
        callback = MagicMock()
        
        watcher.add_watch("/config/app.json", callback)
        watcher.remove_watch("/config/app.json", callback)
        
        assert "/config/app.json" not in watcher._watched_files
    
    @pytest.mark.asyncio
    async def test_file_change_notification(self, watcher):
        """Test file change notification."""
        callback = AsyncMock()
        file_path = "/config/app.json"
        
        watcher.add_watch(file_path, callback)
        
        # Simulate file change
        await watcher._notify_change(file_path, "modified")
        
        callback.assert_called_once()
        call_args = callback.call_args[0]
        assert call_args[0] == file_path
        assert call_args[1] == "modified"
    
    @pytest.mark.asyncio
    async def test_start_stop_watcher(self, watcher):
        """Test starting and stopping watcher."""
        with patch("watchdog.observers.Observer") as mock_observer_class:
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            
            await watcher.start()
            
            assert watcher._observer is not None
            mock_observer.start.assert_called_once()
            
            await watcher.stop()
            
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()


class TestConfigManager:
    """Test configuration manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create configuration manager."""
        return ConfigManager()
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert isinstance(manager.loader, ConfigLoader)
        assert isinstance(manager.cache, ConfigCache)
        assert isinstance(manager.watcher, ConfigWatcher)
        assert manager._config == {}
        assert len(manager._change_listeners) == 0
    
    def test_add_config_source(self, manager):
        """Test adding configuration source."""
        source = ConfigSource("app", "/config/app.json", ConfigFormat.JSON)
        
        manager.add_source(source)
        
        assert len(manager.loader.sources) == 1
        assert manager.loader.sources[0] == source
    
    @pytest.mark.asyncio
    async def test_load_configuration(self, manager):
        """Test loading configuration."""
        config_data = {
            "app_name": "test_app",
            "debug": True,
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        source = ConfigSource("app", "/config/app.json", ConfigFormat.JSON)
        manager.add_source(source)
        
        with patch.object(manager.loader, "load", return_value=config_data):
            await manager.load()
            
            assert manager._config == config_data
            assert manager.get("app_name") == "test_app"
            assert manager.get("debug") is True
            assert manager.get("database.host") == "localhost"
    
    def test_get_config_values(self, manager):
        """Test getting configuration values."""
        manager._config = {
            "app_name": "test_app",
            "debug": True,
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {
                    "username": "user",
                    "password": "pass"
                }
            },
            "features": ["feature1", "feature2"]
        }
        
        # Simple key
        assert manager.get("app_name") == "test_app"
        assert manager.get("debug") is True
        
        # Nested key with dot notation
        assert manager.get("database.host") == "localhost"
        assert manager.get("database.port") == 5432
        assert manager.get("database.credentials.username") == "user"
        
        # Array access
        assert manager.get("features.0") == "feature1"
        assert manager.get("features.1") == "feature2"
        
        # Non-existent key with default
        assert manager.get("nonexistent", "default") == "default"
        assert manager.get("database.nonexistent", None) is None
    
    def test_set_config_values(self, manager):
        """Test setting configuration values."""
        manager._config = {"app_name": "old_app"}
        
        # Simple key
        manager.set("app_name", "new_app")
        assert manager.get("app_name") == "new_app"
        
        # Nested key
        manager.set("database.host", "new_host")
        assert manager.get("database.host") == "new_host"
        
        # Deep nested key
        manager.set("cache.redis.host", "redis_host")
        assert manager.get("cache.redis.host") == "redis_host"
    
    def test_has_config_key(self, manager):
        """Test checking if configuration key exists."""
        manager._config = {
            "app_name": "test_app",
            "database": {
                "host": "localhost"
            }
        }
        
        assert manager.has("app_name") is True
        assert manager.has("database.host") is True
        assert manager.has("nonexistent") is False
        assert manager.has("database.nonexistent") is False
    
    def test_delete_config_key(self, manager):
        """Test deleting configuration key."""
        manager._config = {
            "app_name": "test_app",
            "debug": True,
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        # Delete simple key
        manager.delete("debug")
        assert manager.has("debug") is False
        
        # Delete nested key
        manager.delete("database.port")
        assert manager.has("database.port") is False
        assert manager.has("database.host") is True  # Other keys remain
    
    def test_config_sections(self, manager):
        """Test getting configuration sections."""
        manager._config = {
            "app_name": "test_app",
            "database": {
                "host": "localhost",
                "port": 5432
            },
            "cache": {
                "type": "redis",
                "ttl": 3600
            }
        }
        
        # Get entire section
        database_config = manager.get_section("database")
        assert database_config == {"host": "localhost", "port": 5432}
        
        cache_config = manager.get_section("cache")
        assert cache_config == {"type": "redis", "ttl": 3600}
        
        # Non-existent section
        assert manager.get_section("nonexistent") == {}
    
    @pytest.mark.asyncio
    async def test_config_change_listeners(self, manager):
        """Test configuration change listeners."""
        change_events = []
        
        async def change_listener(event: ConfigChangeEvent):
            change_events.append(event)
        
        manager.add_change_listener(change_listener)
        
        # Simulate configuration change
        old_config = {"debug": False}
        new_config = {"debug": True}
        
        manager._config = old_config
        await manager._notify_change("debug", False, True)
        
        assert len(change_events) == 1
        event = change_events[0]
        assert event.path == "debug"
        assert event.old_value is False
        assert event.new_value is True
    
    @pytest.mark.asyncio
    async def test_auto_reload_on_file_change(self, manager):
        """Test automatic reload on file change."""
        config_data = {"version": "1.0"}
        updated_config = {"version": "2.0"}
        
        source = ConfigSource("app", "/config/app.json", ConfigFormat.JSON)
        manager.add_source(source)
        manager.enable_auto_reload()
        
        with patch.object(manager.loader, "load") as mock_load:
            mock_load.side_effect = [config_data, updated_config]
            
            # Initial load
            await manager.load()
            assert manager.get("version") == "1.0"
            
            # Simulate file change
            await manager._handle_file_change("/config/app.json", "modified")
            
            assert manager.get("version") == "2.0"
            assert mock_load.call_count == 2
    
    def test_config_validation(self, manager):
        """Test configuration validation."""
        def validate_app_config(config: Dict[str, Any]) -> None:
            if "app_name" not in config:
                raise ValueError("app_name is required")
            if not isinstance(config.get("port"), int):
                raise ValueError("port must be an integer")
        
        manager.add_validator(validate_app_config)
        
        # Valid configuration
        valid_config = {"app_name": "test_app", "port": 8000}
        manager._validate_config(valid_config)  # Should not raise
        
        # Invalid configuration
        invalid_config = {"port": "not_an_integer"}
        with pytest.raises(ConfigValidationError):
            manager._validate_config(invalid_config)
    
    def test_config_environment_substitution(self, manager):
        """Test environment variable substitution in configuration."""
        import os
        
        config_with_env = {
            "database_url": "${DATABASE_URL}",
            "api_key": "${API_KEY:default_key}",
            "debug": "${DEBUG:false}"
        }
        
        env_vars = {
            "DATABASE_URL": "postgresql://localhost/testdb",
            "API_KEY": "secret_key"
            # DEBUG not set, should use default
        }
        
        with patch.dict(os.environ, env_vars):
            resolved = manager._resolve_environment_variables(config_with_env)
            
            assert resolved["database_url"] == "postgresql://localhost/testdb"
            assert resolved["api_key"] == "secret_key"
            assert resolved["debug"] == "false"  # Default value
    
    def test_config_merge_strategies(self, manager):
        """Test different configuration merge strategies."""
        base_config = {
            "app_name": "base_app",
            "features": ["feature1", "feature2"],
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        override_config = {
            "app_name": "override_app",
            "features": ["feature3"],
            "database": {
                "host": "remote_host"
            },
            "new_setting": "new_value"
        }
        
        # Deep merge (default)
        merged = manager._merge_configs(base_config, override_config, strategy="deep")
        
        assert merged["app_name"] == "override_app"
        assert merged["features"] == ["feature3"]  # Replaced
        assert merged["database"]["host"] == "remote_host"  # Overridden
        assert merged["database"]["port"] == 5432  # Preserved
        assert merged["new_setting"] == "new_value"  # Added
        
        # Shallow merge
        merged = manager._merge_configs(base_config, override_config, strategy="shallow")
        
        assert merged["database"] == {"host": "remote_host"}  # Completely replaced
    
    @pytest.mark.asyncio
    async def test_config_backup_and_restore(self, manager):
        """Test configuration backup and restore."""
        original_config = {
            "app_name": "original_app",
            "debug": False
        }
        
        manager._config = original_config.copy()
        
        # Create backup
        backup_id = await manager.create_backup("before_changes")
        
        # Modify configuration
        manager.set("debug", True)
        manager.set("new_feature", True)
        
        assert manager.get("debug") is True
        assert manager.get("new_feature") is True
        
        # Restore from backup
        await manager.restore_backup(backup_id)
        
        assert manager.get("debug") is False
        assert manager.has("new_feature") is False
        assert manager._config == original_config
    
    def test_config_export_import(self, manager):
        """Test configuration export and import."""
        config_data = {
            "app_name": "export_app",
            "version": "1.0",
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        
        manager._config = config_data
        
        # Export configuration
        exported = manager.export_config(format="json")
        
        # Import into new manager
        new_manager = ConfigManager()
        new_manager.import_config(exported, format="json")
        
        assert new_manager._config == config_data
        assert new_manager.get("app_name") == "export_app"
        assert new_manager.get("database.host") == "localhost"
    
    def test_config_diff(self, manager):
        """Test configuration difference detection."""
        old_config = {
            "app_name": "old_app",
            "debug": False,
            "database": {
                "host": "localhost"
            }
        }
        
        new_config = {
            "app_name": "new_app",
            "debug": False,
            "database": {
                "host": "remote_host",
                "port": 5432
            },
            "new_feature": True
        }
        
        diff = manager._compute_config_diff(old_config, new_config)
        
        assert "app_name" in diff["changed"]
        assert diff["changed"]["app_name"]["old"] == "old_app"
        assert diff["changed"]["app_name"]["new"] == "new_app"
        
        assert "database.host" in diff["changed"]
        assert "database.port" in diff["added"]
        assert "new_feature" in diff["added"]
