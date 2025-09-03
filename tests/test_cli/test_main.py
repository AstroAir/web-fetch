"""
Comprehensive tests for the CLI main module.
"""

import pytest
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO
from pathlib import Path

from web_fetch.cli.main import (
    main,
    create_parser,
    handle_fetch_command,
    handle_batch_command,
    handle_config_command,
    handle_monitor_command,
    setup_logging_from_args,
)
from web_fetch.models.http import FetchResult
from web_fetch.models.base import ContentType


class TestCLIParser:
    """Test CLI argument parser."""

    def test_create_parser(self):
        """Test creating the argument parser."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "web-fetch"

    def test_parse_basic_fetch_command(self):
        """Test parsing basic fetch command."""
        parser = create_parser()
        args = parser.parse_args(["fetch", "https://example.com"])
        
        assert args.command == "fetch"
        assert args.url == "https://example.com"
        assert args.output_format == "text"
        assert args.verbose == False

    def test_parse_fetch_with_options(self):
        """Test parsing fetch command with options."""
        parser = create_parser()
        args = parser.parse_args([
            "fetch",
            "https://example.com",
            "--format", "json",
            "--output", "result.json",
            "--timeout", "30",
            "--retries", "5",
            "--verbose"
        ])
        
        assert args.command == "fetch"
        assert args.url == "https://example.com"
        assert args.output_format == "json"
        assert args.output == "result.json"
        assert args.timeout == 30
        assert args.retries == 5
        assert args.verbose == True

    def test_parse_batch_command(self):
        """Test parsing batch command."""
        parser = create_parser()
        args = parser.parse_args([
            "batch",
            "--urls-file", "urls.txt",
            "--concurrency", "10",
            "--output-dir", "results/"
        ])
        
        assert args.command == "batch"
        assert args.urls_file == "urls.txt"
        assert args.concurrency == 10
        assert args.output_dir == "results/"

    def test_parse_config_command(self):
        """Test parsing config command."""
        parser = create_parser()
        args = parser.parse_args([
            "config",
            "--set", "timeout=30",
            "--get", "retries"
        ])
        
        assert args.command == "config"
        assert args.set == "timeout=30"
        assert args.get == "retries"

    def test_parse_monitor_command(self):
        """Test parsing monitor command."""
        parser = create_parser()
        args = parser.parse_args([
            "monitor",
            "--interval", "5",
            "--output", "metrics.json"
        ])
        
        assert args.command == "monitor"
        assert args.interval == 5
        assert args.output == "metrics.json"

    def test_parse_invalid_command(self):
        """Test parsing invalid command."""
        parser = create_parser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(["invalid-command"])

    def test_parse_missing_required_args(self):
        """Test parsing with missing required arguments."""
        parser = create_parser()
        
        # Fetch command requires URL
        with pytest.raises(SystemExit):
            parser.parse_args(["fetch"])

    def test_parse_help_option(self):
        """Test parsing help option."""
        parser = create_parser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_parse_version_option(self):
        """Test parsing version option."""
        parser = create_parser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


class TestFetchCommand:
    """Test fetch command handling."""

    @pytest.mark.asyncio
    async def test_handle_fetch_command_success(self):
        """Test successful fetch command."""
        # Mock arguments
        args = MagicMock()
        args.url = "https://example.com"
        args.output_format = "text"
        args.output = None
        args.timeout = 30
        args.retries = 3
        args.headers = None
        args.user_agent = None
        
        # Mock fetch result
        mock_result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={"content-type": "text/plain"},
            content="Hello, World!",
            content_type=ContentType.TEXT
        )
        
        with patch('web_fetch.cli.main.fetch_url', return_value=mock_result) as mock_fetch:
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await handle_fetch_command(args)
                
                mock_fetch.assert_called_once()
                output = mock_stdout.getvalue()
                assert "Hello, World!" in output

    @pytest.mark.asyncio
    async def test_handle_fetch_command_json_output(self):
        """Test fetch command with JSON output."""
        args = MagicMock()
        args.url = "https://api.example.com/data"
        args.output_format = "json"
        args.output = None
        args.timeout = 30
        args.retries = 3
        args.headers = None
        args.user_agent = None
        
        mock_result = FetchResult(
            url="https://api.example.com/data",
            status_code=200,
            headers={"content-type": "application/json"},
            content='{"message": "success"}',
            content_type=ContentType.JSON
        )
        
        with patch('web_fetch.cli.main.fetch_url', return_value=mock_result):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await handle_fetch_command(args)
                
                output = mock_stdout.getvalue()
                assert '"message": "success"' in output

    @pytest.mark.asyncio
    async def test_handle_fetch_command_with_output_file(self):
        """Test fetch command with output file."""
        args = MagicMock()
        args.url = "https://example.com"
        args.output_format = "text"
        args.output = "output.txt"
        args.timeout = 30
        args.retries = 3
        args.headers = None
        args.user_agent = None
        
        mock_result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={"content-type": "text/plain"},
            content="File content",
            content_type=ContentType.TEXT
        )
        
        with patch('web_fetch.cli.main.fetch_url', return_value=mock_result):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                await handle_fetch_command(args)
                
                mock_open.assert_called_with("output.txt", "w", encoding="utf-8")
                mock_file.write.assert_called_with("File content")

    @pytest.mark.asyncio
    async def test_handle_fetch_command_with_custom_headers(self):
        """Test fetch command with custom headers."""
        args = MagicMock()
        args.url = "https://api.example.com"
        args.output_format = "text"
        args.output = None
        args.timeout = 30
        args.retries = 3
        args.headers = ["Authorization: Bearer token", "Accept: application/json"]
        args.user_agent = "custom-agent/1.0"
        
        mock_result = FetchResult(
            url="https://api.example.com",
            status_code=200,
            headers={},
            content="API response",
            content_type=ContentType.TEXT
        )
        
        with patch('web_fetch.cli.main.fetch_url', return_value=mock_result) as mock_fetch:
            with patch('sys.stdout', new_callable=StringIO):
                await handle_fetch_command(args)
                
                # Check that custom headers were passed
                call_args = mock_fetch.call_args
                config = call_args[1]['config']
                assert config.headers is not None

    @pytest.mark.asyncio
    async def test_handle_fetch_command_error(self):
        """Test fetch command with error."""
        args = MagicMock()
        args.url = "https://nonexistent.example.com"
        args.output_format = "text"
        args.output = None
        args.timeout = 30
        args.retries = 3
        args.headers = None
        args.user_agent = None
        
        with patch('web_fetch.cli.main.fetch_url', side_effect=Exception("Connection failed")):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit):
                    await handle_fetch_command(args)
                
                error_output = mock_stderr.getvalue()
                assert "Connection failed" in error_output


class TestBatchCommand:
    """Test batch command handling."""

    @pytest.mark.asyncio
    async def test_handle_batch_command_from_file(self):
        """Test batch command reading URLs from file."""
        args = MagicMock()
        args.urls_file = "urls.txt"
        args.urls = None
        args.concurrency = 5
        args.output_dir = "results/"
        args.output_format = "json"
        args.timeout = 30
        args.retries = 3
        
        # Mock file content
        urls_content = "https://example.com/1\nhttps://example.com/2\nhttps://example.com/3"
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = urls_content
            
            with patch('web_fetch.cli.main.BatchManager') as mock_manager_class:
                mock_manager = AsyncMock()
                mock_manager_class.return_value.__aenter__.return_value = mock_manager
                
                # Mock successful batch result
                mock_result = MagicMock()
                mock_result.results = []
                mock_result.success_count = 3
                mock_result.failure_count = 0
                mock_manager.process_urls_and_wait.return_value = mock_result
                
                await handle_batch_command(args)
                
                mock_manager.process_urls_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_batch_command_from_args(self):
        """Test batch command with URLs from arguments."""
        args = MagicMock()
        args.urls_file = None
        args.urls = ["https://example.com/1", "https://example.com/2"]
        args.concurrency = 5
        args.output_dir = "results/"
        args.output_format = "json"
        args.timeout = 30
        args.retries = 3
        
        with patch('web_fetch.cli.main.BatchManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            
            mock_result = MagicMock()
            mock_result.results = []
            mock_result.success_count = 2
            mock_result.failure_count = 0
            mock_manager.process_urls_and_wait.return_value = mock_result
            
            await handle_batch_command(args)
            
            mock_manager.process_urls_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_batch_command_missing_urls(self):
        """Test batch command with missing URLs."""
        args = MagicMock()
        args.urls_file = None
        args.urls = None
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit):
                await handle_batch_command(args)
            
            error_output = mock_stderr.getvalue()
            assert "URLs" in error_output


class TestConfigCommand:
    """Test config command handling."""

    @pytest.mark.asyncio
    async def test_handle_config_command_get(self):
        """Test config command get operation."""
        args = MagicMock()
        args.get = "timeout"
        args.set = None
        args.list = False
        args.reset = None
        
        with patch('web_fetch.cli.main.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            mock_config.get.return_value = 30
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await handle_config_command(args)
                
                output = mock_stdout.getvalue()
                assert "30" in output

    @pytest.mark.asyncio
    async def test_handle_config_command_set(self):
        """Test config command set operation."""
        args = MagicMock()
        args.get = None
        args.set = "timeout=60"
        args.list = False
        args.reset = None
        
        with patch('web_fetch.cli.main.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await handle_config_command(args)
                
                mock_config.set.assert_called_with("timeout", "60")

    @pytest.mark.asyncio
    async def test_handle_config_command_list(self):
        """Test config command list operation."""
        args = MagicMock()
        args.get = None
        args.set = None
        args.list = True
        args.reset = None
        
        with patch('web_fetch.cli.main.ConfigManager') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            mock_config.list_all.return_value = {"timeout": 30, "retries": 3}
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await handle_config_command(args)
                
                output = mock_stdout.getvalue()
                assert "timeout" in output
                assert "retries" in output


class TestMonitorCommand:
    """Test monitor command handling."""

    @pytest.mark.asyncio
    async def test_handle_monitor_command(self):
        """Test monitor command."""
        args = MagicMock()
        args.interval = 5
        args.output = None
        args.duration = 10
        
        with patch('web_fetch.cli.main.MetricsCollector') as mock_metrics_class:
            mock_metrics = MagicMock()
            mock_metrics_class.return_value = mock_metrics
            mock_metrics.get_current_metrics.return_value = {
                "requests_per_second": 10.5,
                "average_response_time": 1.2,
                "success_rate": 0.95
            }
            
            with patch('asyncio.sleep', side_effect=[None, KeyboardInterrupt()]):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    await handle_monitor_command(args)
                    
                    output = mock_stdout.getvalue()
                    assert "requests_per_second" in output


class TestLoggingSetup:
    """Test logging setup."""

    def test_setup_logging_verbose(self):
        """Test setting up verbose logging."""
        args = MagicMock()
        args.verbose = True
        args.quiet = False
        args.log_file = None
        
        with patch('web_fetch.cli.main.logging') as mock_logging:
            setup_logging_from_args(args)
            
            mock_logging.basicConfig.assert_called_once()

    def test_setup_logging_quiet(self):
        """Test setting up quiet logging."""
        args = MagicMock()
        args.verbose = False
        args.quiet = True
        args.log_file = None
        
        with patch('web_fetch.cli.main.logging') as mock_logging:
            setup_logging_from_args(args)
            
            mock_logging.basicConfig.assert_called_once()

    def test_setup_logging_with_file(self):
        """Test setting up logging with file output."""
        args = MagicMock()
        args.verbose = False
        args.quiet = False
        args.log_file = "app.log"
        
        with patch('web_fetch.cli.main.logging') as mock_logging:
            setup_logging_from_args(args)
            
            mock_logging.basicConfig.assert_called_once()


class TestMainFunction:
    """Test main function."""

    @pytest.mark.asyncio
    async def test_main_function_fetch(self):
        """Test main function with fetch command."""
        test_args = ["web-fetch", "fetch", "https://example.com"]
        
        with patch('sys.argv', test_args):
            with patch('web_fetch.cli.main.handle_fetch_command') as mock_handle:
                with patch('web_fetch.cli.main.setup_logging_from_args'):
                    await main()
                    
                    mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_function_batch(self):
        """Test main function with batch command."""
        test_args = ["web-fetch", "batch", "--urls", "https://example.com"]
        
        with patch('sys.argv', test_args):
            with patch('web_fetch.cli.main.handle_batch_command') as mock_handle:
                with patch('web_fetch.cli.main.setup_logging_from_args'):
                    await main()
                    
                    mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_function_error_handling(self):
        """Test main function error handling."""
        test_args = ["web-fetch", "fetch", "https://example.com"]
        
        with patch('sys.argv', test_args):
            with patch('web_fetch.cli.main.handle_fetch_command', side_effect=Exception("Test error")):
                with patch('web_fetch.cli.main.setup_logging_from_args'):
                    with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                        with pytest.raises(SystemExit):
                            await main()
                        
                        error_output = mock_stderr.getvalue()
                        assert "Test error" in error_output
