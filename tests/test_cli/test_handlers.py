"""
Comprehensive tests for the CLI handlers module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from web_fetch.cli.handlers import (
    FetchHandler,
    BatchHandler,
    ConfigHandler,
    MonitorHandler,
    CacheHandler,
    TestHandler,
)
from web_fetch.models.http import FetchResult, FetchConfig
from web_fetch.models.base import ContentType
from web_fetch.batch.models import BatchResult, BatchStatus


class TestFetchHandler:
    """Test fetch command handler."""

    @pytest.mark.asyncio
    async def test_fetch_handler_basic(self):
        """Test basic fetch operation."""
        handler = FetchHandler()
        
        # Mock successful fetch
        mock_result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={"content-type": "text/plain"},
            content="Hello, World!",
            content_type=ContentType.TEXT
        )
        
        with patch('web_fetch.cli.handlers.fetch_url', return_value=mock_result) as mock_fetch:
            result = await handler.handle_fetch(
                url="https://example.com",
                output_format="text"
            )
            
            assert result == mock_result
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_handler_with_config(self):
        """Test fetch with custom configuration."""
        handler = FetchHandler()
        
        config = FetchConfig(
            total_timeout=60.0,
            max_retries=5
        )
        
        mock_result = FetchResult(
            url="https://api.example.com",
            status_code=200,
            headers={},
            content='{"data": "value"}',
            content_type=ContentType.JSON
        )
        
        with patch('web_fetch.cli.handlers.fetch_url', return_value=mock_result) as mock_fetch:
            result = await handler.handle_fetch(
                url="https://api.example.com",
                output_format="json",
                config=config
            )
            
            assert result == mock_result
            mock_fetch.assert_called_with("https://api.example.com", config=config)

    @pytest.mark.asyncio
    async def test_fetch_handler_with_headers(self):
        """Test fetch with custom headers."""
        handler = FetchHandler()
        
        headers = {
            "Authorization": "Bearer token",
            "Accept": "application/json"
        }
        
        mock_result = FetchResult(
            url="https://api.example.com",
            status_code=200,
            headers={},
            content='{"authenticated": true}',
            content_type=ContentType.JSON
        )
        
        with patch('web_fetch.cli.handlers.fetch_url', return_value=mock_result) as mock_fetch:
            result = await handler.handle_fetch(
                url="https://api.example.com",
                output_format="json",
                headers=headers
            )
            
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_fetch_handler_error(self):
        """Test fetch handler error handling."""
        handler = FetchHandler()
        
        with patch('web_fetch.cli.handlers.fetch_url', side_effect=Exception("Network error")):
            with pytest.raises(Exception, match="Network error"):
                await handler.handle_fetch(
                    url="https://nonexistent.example.com",
                    output_format="text"
                )

    @pytest.mark.asyncio
    async def test_fetch_handler_save_to_file(self):
        """Test saving fetch result to file."""
        handler = FetchHandler()
        
        mock_result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={},
            content="File content",
            content_type=ContentType.TEXT
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            with patch('web_fetch.cli.handlers.fetch_url', return_value=mock_result):
                result = await handler.handle_fetch(
                    url="https://example.com",
                    output_format="text",
                    output_file=tmp_file.name
                )
                
                assert result == mock_result
                
                # Verify file was written
                with open(tmp_file.name, 'r') as f:
                    content = f.read()
                    assert content == "File content"


class TestBatchHandler:
    """Test batch command handler."""

    @pytest.mark.asyncio
    async def test_batch_handler_from_urls(self):
        """Test batch processing from URL list."""
        handler = BatchHandler()
        
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3"
        ]
        
        # Mock batch result
        mock_results = [
            FetchResult(
                url=url,
                status_code=200,
                headers={},
                content=f"content {i}",
                content_type=ContentType.TEXT
            )
            for i, url in enumerate(urls, 1)
        ]
        
        mock_batch_result = BatchResult(
            batch_id="test-batch",
            results=mock_results,
            status=BatchStatus.COMPLETED
        )
        
        with patch('web_fetch.cli.handlers.BatchManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            mock_manager.process_urls_and_wait.return_value = mock_batch_result
            
            result = await handler.handle_batch(
                urls=urls,
                concurrency=5,
                output_format="json"
            )
            
            assert result == mock_batch_result
            mock_manager.process_urls_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_handler_from_file(self):
        """Test batch processing from file."""
        handler = BatchHandler()
        
        urls_content = "https://example.com/1\nhttps://example.com/2\nhttps://example.com/3"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write(urls_content)
            tmp_file.flush()
            
            mock_batch_result = BatchResult(
                batch_id="test-batch",
                results=[],
                status=BatchStatus.COMPLETED
            )
            
            with patch('web_fetch.cli.handlers.BatchManager') as mock_manager_class:
                mock_manager = AsyncMock()
                mock_manager_class.return_value.__aenter__.return_value = mock_manager
                mock_manager.process_urls_and_wait.return_value = mock_batch_result
                
                result = await handler.handle_batch(
                    urls_file=tmp_file.name,
                    concurrency=10,
                    output_format="json"
                )
                
                assert result == mock_batch_result

    @pytest.mark.asyncio
    async def test_batch_handler_with_progress(self):
        """Test batch processing with progress callback."""
        handler = BatchHandler()
        
        progress_updates = []
        
        def progress_callback(batch_id, completed, total, current_url=None):
            progress_updates.append((batch_id, completed, total, current_url))
        
        urls = ["https://example.com/1", "https://example.com/2"]
        
        mock_batch_result = BatchResult(
            batch_id="test-batch",
            results=[],
            status=BatchStatus.COMPLETED
        )
        
        with patch('web_fetch.cli.handlers.BatchManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            mock_manager.process_urls_and_wait.return_value = mock_batch_result
            
            result = await handler.handle_batch(
                urls=urls,
                concurrency=5,
                output_format="json",
                progress_callback=progress_callback
            )
            
            assert result == mock_batch_result

    @pytest.mark.asyncio
    async def test_batch_handler_save_results(self):
        """Test saving batch results to directory."""
        handler = BatchHandler()
        
        urls = ["https://example.com/1"]
        
        mock_results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
        ]
        
        mock_batch_result = BatchResult(
            batch_id="test-batch",
            results=mock_results,
            status=BatchStatus.COMPLETED
        )
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('web_fetch.cli.handlers.BatchManager') as mock_manager_class:
                mock_manager = AsyncMock()
                mock_manager_class.return_value.__aenter__.return_value = mock_manager
                mock_manager.process_urls_and_wait.return_value = mock_batch_result
                
                result = await handler.handle_batch(
                    urls=urls,
                    concurrency=5,
                    output_format="json",
                    output_dir=tmp_dir
                )
                
                assert result == mock_batch_result


class TestConfigHandler:
    """Test config command handler."""

    def test_config_handler_get(self):
        """Test getting configuration value."""
        handler = ConfigHandler()
        
        with patch('web_fetch.cli.handlers.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            mock_config.get.return_value = 30
            
            result = handler.handle_get_config("timeout")
            
            assert result == 30
            mock_config.get.assert_called_with("timeout")

    def test_config_handler_set(self):
        """Test setting configuration value."""
        handler = ConfigHandler()
        
        with patch('web_fetch.cli.handlers.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            
            handler.handle_set_config("timeout", "60")
            
            mock_config.set.assert_called_with("timeout", "60")

    def test_config_handler_list(self):
        """Test listing all configuration values."""
        handler = ConfigHandler()
        
        expected_config = {
            "timeout": 30,
            "retries": 3,
            "user_agent": "web-fetch/1.0"
        }
        
        with patch('web_fetch.cli.handlers.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            mock_config.list_all.return_value = expected_config
            
            result = handler.handle_list_config()
            
            assert result == expected_config
            mock_config.list_all.assert_called_once()

    def test_config_handler_reset(self):
        """Test resetting configuration value."""
        handler = ConfigHandler()
        
        with patch('web_fetch.cli.handlers.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            
            handler.handle_reset_config("timeout")
            
            mock_config.reset.assert_called_with("timeout")

    def test_config_handler_validate(self):
        """Test validating configuration."""
        handler = ConfigHandler()
        
        with patch('web_fetch.cli.handlers.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            mock_config.validate.return_value = True
            
            result = handler.handle_validate_config()
            
            assert result == True
            mock_config.validate.assert_called_once()


class TestMonitorHandler:
    """Test monitor command handler."""

    @pytest.mark.asyncio
    async def test_monitor_handler_basic(self):
        """Test basic monitoring."""
        handler = MonitorHandler()
        
        mock_metrics = {
            "requests_per_second": 10.5,
            "average_response_time": 1.2,
            "success_rate": 0.95,
            "active_connections": 5
        }
        
        with patch('web_fetch.cli.handlers.MetricsCollector') as mock_collector_class:
            mock_collector = MagicMock()
            mock_collector_class.return_value = mock_collector
            mock_collector.get_current_metrics.return_value = mock_metrics
            
            # Mock sleep to prevent infinite loop
            with patch('asyncio.sleep', side_effect=[None, KeyboardInterrupt()]):
                metrics_list = []
                
                async def collect_metrics():
                    async for metrics in handler.monitor_metrics(interval=1):
                        metrics_list.append(metrics)
                
                with pytest.raises(KeyboardInterrupt):
                    await collect_metrics()
                
                assert len(metrics_list) >= 1
                assert metrics_list[0] == mock_metrics

    @pytest.mark.asyncio
    async def test_monitor_handler_with_duration(self):
        """Test monitoring with duration limit."""
        handler = MonitorHandler()
        
        mock_metrics = {"requests_per_second": 5.0}
        
        with patch('web_fetch.cli.handlers.MetricsCollector') as mock_collector_class:
            mock_collector = MagicMock()
            mock_collector_class.return_value = mock_collector
            mock_collector.get_current_metrics.return_value = mock_metrics
            
            metrics_list = []
            
            async for metrics in handler.monitor_metrics(interval=0.1, duration=0.2):
                metrics_list.append(metrics)
            
            assert len(metrics_list) >= 1

    @pytest.mark.asyncio
    async def test_monitor_handler_save_to_file(self):
        """Test saving monitoring data to file."""
        handler = MonitorHandler()
        
        mock_metrics = {"timestamp": "2023-01-01T00:00:00", "requests": 100}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            with patch('web_fetch.cli.handlers.MetricsCollector') as mock_collector_class:
                mock_collector = MagicMock()
                mock_collector_class.return_value = mock_collector
                mock_collector.get_current_metrics.return_value = mock_metrics
                
                await handler.save_metrics_to_file([mock_metrics], tmp_file.name)
                
                # Verify file content
                with open(tmp_file.name, 'r') as f:
                    content = f.read()
                    data = json.loads(content)
                    assert len(data) == 1
                    assert data[0]["requests"] == 100


class TestCacheHandler:
    """Test cache command handler."""

    @pytest.mark.asyncio
    async def test_cache_handler_clear(self):
        """Test clearing cache."""
        handler = CacheHandler()
        
        with patch('web_fetch.cli.handlers.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache
            
            await handler.handle_clear_cache()
            
            mock_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_handler_stats(self):
        """Test getting cache statistics."""
        handler = CacheHandler()
        
        expected_stats = {
            "size": 150,
            "max_size": 1000,
            "hit_rate": 0.85,
            "miss_rate": 0.15
        }
        
        with patch('web_fetch.cli.handlers.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache
            mock_cache.get_stats.return_value = expected_stats
            
            stats = await handler.handle_cache_stats()
            
            assert stats == expected_stats
            mock_cache.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_handler_list_keys(self):
        """Test listing cache keys."""
        handler = CacheHandler()
        
        expected_keys = [
            "https://example.com/1",
            "https://example.com/2",
            "https://api.example.com/data"
        ]
        
        with patch('web_fetch.cli.handlers.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache
            mock_cache.list_keys.return_value = expected_keys
            
            keys = await handler.handle_list_cache_keys()
            
            assert keys == expected_keys
            mock_cache.list_keys.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_handler_remove_key(self):
        """Test removing specific cache key."""
        handler = CacheHandler()
        
        with patch('web_fetch.cli.handlers.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache
            mock_cache.remove.return_value = True
            
            result = await handler.handle_remove_cache_key("https://example.com")
            
            assert result == True
            mock_cache.remove.assert_called_with("https://example.com")


class TestTestHandler:
    """Test test command handler."""

    @pytest.mark.asyncio
    async def test_test_handler_connectivity(self):
        """Test connectivity testing."""
        handler = TestHandler()
        
        mock_result = FetchResult(
            url="https://httpbin.org/get",
            status_code=200,
            headers={},
            content='{"origin": "127.0.0.1"}',
            content_type=ContentType.JSON
        )
        
        with patch('web_fetch.cli.handlers.fetch_url', return_value=mock_result) as mock_fetch:
            result = await handler.test_connectivity()
            
            assert result["success"] == True
            assert result["status_code"] == 200
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_handler_connectivity_failure(self):
        """Test connectivity testing with failure."""
        handler = TestHandler()
        
        with patch('web_fetch.cli.handlers.fetch_url', side_effect=Exception("Connection failed")):
            result = await handler.test_connectivity()
            
            assert result["success"] == False
            assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_test_handler_performance(self):
        """Test performance testing."""
        handler = TestHandler()
        
        mock_results = [
            FetchResult(
                url="https://httpbin.org/get",
                status_code=200,
                headers={},
                content="{}",
                content_type=ContentType.JSON
            )
            for _ in range(5)
        ]
        
        with patch('web_fetch.cli.handlers.fetch_url', side_effect=mock_results):
            result = await handler.test_performance(num_requests=5)
            
            assert result["total_requests"] == 5
            assert result["successful_requests"] == 5
            assert result["failed_requests"] == 0
            assert "average_response_time" in result
            assert "requests_per_second" in result

    @pytest.mark.asyncio
    async def test_test_handler_features(self):
        """Test feature testing."""
        handler = TestHandler()
        
        with patch('web_fetch.cli.handlers.fetch_url') as mock_fetch:
            # Mock different responses for different tests
            mock_fetch.side_effect = [
                # HTTP test
                FetchResult(url="http://httpbin.org/get", status_code=200, headers={}, content="{}", content_type=ContentType.JSON),
                # HTTPS test
                FetchResult(url="https://httpbin.org/get", status_code=200, headers={}, content="{}", content_type=ContentType.JSON),
                # JSON test
                FetchResult(url="https://httpbin.org/json", status_code=200, headers={}, content='{"test": true}', content_type=ContentType.JSON),
            ]
            
            result = await handler.test_features()
            
            assert "http_support" in result
            assert "https_support" in result
            assert "json_parsing" in result
            assert result["http_support"]["success"] == True
            assert result["https_support"]["success"] == True
            assert result["json_parsing"]["success"] == True
