"""
Unit tests for streaming functionality.

Tests for the StreamingWebFetcher class, streaming operations, and progress tracking.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from web_fetch.fetcher import StreamingWebFetcher, download_file
from web_fetch.models import (
    ProgressInfo,
    StreamingConfig,
    StreamRequest,
)


class TestStreamingConfig:
    """Test the StreamingConfig model."""
    
    def test_default_config(self):
        """Test default streaming configuration."""
        config = StreamingConfig()
        assert config.chunk_size == 8192
        assert config.buffer_size == 64 * 1024
        assert config.enable_progress is True
        assert config.progress_interval == 0.1
        assert config.max_file_size is None
    
    def test_custom_config(self):
        """Test custom streaming configuration."""
        config = StreamingConfig(
            chunk_size=16384,
            buffer_size=128 * 1024,
            enable_progress=False,
            progress_interval=0.5,
            max_file_size=10 * 1024 * 1024
        )
        assert config.chunk_size == 16384
        assert config.buffer_size == 128 * 1024
        assert config.enable_progress is False
        assert config.progress_interval == 0.5
        assert config.max_file_size == 10 * 1024 * 1024
    
    def test_validation(self):
        """Test configuration validation."""
        # Chunk size too small
        with pytest.raises(ValueError):
            StreamingConfig(chunk_size=512)
        
        # Chunk size too large
        with pytest.raises(ValueError):
            StreamingConfig(chunk_size=2 * 1024 * 1024)
        
        # Progress interval too small
        with pytest.raises(ValueError):
            StreamingConfig(progress_interval=0.005)


class TestProgressInfo:
    """Test the ProgressInfo dataclass."""
    
    def test_progress_properties(self):
        """Test progress info properties."""
        progress = ProgressInfo(
            bytes_downloaded=1024,
            total_bytes=2048,
            chunk_count=2,
            elapsed_time=1.0,
            download_speed=1024.0,
            eta=1.0,
            percentage=50.0
        )
        
        assert progress.bytes_downloaded == 1024
        assert progress.total_bytes == 2048
        assert progress.percentage == 50.0
        assert progress.is_complete is False
        assert progress.speed_human == "1.0 KB/s"
    
    def test_completion_check(self):
        """Test completion checking."""
        # Complete download
        complete_progress = ProgressInfo(
            bytes_downloaded=2048,
            total_bytes=2048,
            chunk_count=4,
            elapsed_time=2.0,
            download_speed=1024.0,
            eta=0.0,
            percentage=100.0
        )
        assert complete_progress.is_complete is True
        
        # Unknown total size
        unknown_progress = ProgressInfo(
            bytes_downloaded=1024,
            total_bytes=None,
            chunk_count=2,
            elapsed_time=1.0,
            download_speed=1024.0,
            eta=None,
            percentage=None
        )
        assert unknown_progress.is_complete is False
    
    def test_speed_formatting(self):
        """Test speed formatting."""
        # Bytes per second
        progress_bytes = ProgressInfo(
            bytes_downloaded=100,
            total_bytes=None,
            chunk_count=1,
            elapsed_time=1.0,
            download_speed=500.0,
            eta=None,
            percentage=None
        )
        assert progress_bytes.speed_human == "500.0 B/s"
        
        # Kilobytes per second
        progress_kb = ProgressInfo(
            bytes_downloaded=1024,
            total_bytes=None,
            chunk_count=1,
            elapsed_time=1.0,
            download_speed=2048.0,
            eta=None,
            percentage=None
        )
        assert progress_kb.speed_human == "2.0 KB/s"
        
        # Megabytes per second
        progress_mb = ProgressInfo(
            bytes_downloaded=1024 * 1024,
            total_bytes=None,
            chunk_count=1,
            elapsed_time=1.0,
            download_speed=2 * 1024 * 1024,
            eta=None,
            percentage=None
        )
        assert progress_mb.speed_human == "2.0 MB/s"


class TestStreamRequest:
    """Test the StreamRequest model."""
    
    def test_valid_stream_request(self):
        """Test valid stream request creation."""
        request = StreamRequest(url="https://example.com/file.zip")
        assert str(request.url) == "https://example.com/file.zip"
        assert request.method == "GET"
        assert request.output_path is None
        assert isinstance(request.streaming_config, StreamingConfig)
    
    def test_stream_request_with_file(self):
        """Test stream request with output file."""
        output_path = Path("/tmp/download.zip")
        request = StreamRequest(
            url="https://example.com/file.zip",
            output_path=output_path
        )
        assert request.output_path == output_path
    
    def test_custom_streaming_config(self):
        """Test stream request with custom config."""
        config = StreamingConfig(chunk_size=16384)
        request = StreamRequest(
            url="https://example.com/file.zip",
            streaming_config=config
        )
        assert request.streaming_config.chunk_size == 16384


class TestStreamingWebFetcher:
    """Test the StreamingWebFetcher class."""
    
    @pytest.mark.asyncio
    async def test_stream_fetch_success(self):
        """Test successful streaming fetch."""
        test_data = b"Hello, World!" * 100  # 1300 bytes
        
        with aioresponses() as m:
            m.get(
                'https://example.com/file.txt',
                body=test_data,
                status=200,
                headers={'Content-Length': str(len(test_data))}
            )
            
            request = StreamRequest(url='https://example.com/file.txt')
            
            async with StreamingWebFetcher() as fetcher:
                result = await fetcher.stream_fetch(request)
            
            assert result.is_success
            assert result.status_code == 200
            assert result.bytes_downloaded == len(test_data)
            assert result.total_bytes == len(test_data)
            assert result.download_complete
    
    @pytest.mark.asyncio
    async def test_stream_fetch_with_file_output(self):
        """Test streaming to file."""
        test_data = b"Test file content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_output.txt"
            
            with aioresponses() as m:
                m.get(
                    'https://example.com/file.txt',
                    body=test_data,
                    status=200,
                    headers={'Content-Length': str(len(test_data))}
                )
                
                request = StreamRequest(
                    url='https://example.com/file.txt',
                    output_path=output_path
                )
                
                async with StreamingWebFetcher() as fetcher:
                    result = await fetcher.stream_fetch(request)
                
                assert result.is_success
                assert result.output_path == output_path
                assert output_path.exists()
                assert output_path.read_bytes() == test_data
    
    @pytest.mark.asyncio
    async def test_stream_fetch_with_progress_callback(self):
        """Test streaming with progress callback."""
        test_data = b"x" * 10000  # 10KB
        progress_calls = []
        
        def progress_callback(progress: ProgressInfo):
            progress_calls.append(progress)
        
        with aioresponses() as m:
            m.get(
                'https://example.com/large_file.bin',
                body=test_data,
                status=200,
                headers={'Content-Length': str(len(test_data))}
            )
            
            streaming_config = StreamingConfig(
                chunk_size=1024,
                progress_interval=0.01  # Very frequent for testing
            )
            
            request = StreamRequest(
                url='https://example.com/large_file.bin',
                streaming_config=streaming_config
            )
            
            async with StreamingWebFetcher() as fetcher:
                result = await fetcher.stream_fetch(request, progress_callback)
            
            assert result.is_success
            assert len(progress_calls) > 0
            
            # Check that progress increased
            if len(progress_calls) > 1:
                assert progress_calls[-1].bytes_downloaded >= progress_calls[0].bytes_downloaded
    
    @pytest.mark.asyncio
    async def test_stream_fetch_file_size_limit(self):
        """Test file size limit enforcement."""
        large_data = b"x" * 1000000  # 1MB
        
        with aioresponses() as m:
            m.get(
                'https://example.com/large_file.bin',
                body=large_data,
                status=200,
                headers={'Content-Length': str(len(large_data))}
            )
            
            streaming_config = StreamingConfig(
                max_file_size=500000  # 500KB limit
            )
            
            request = StreamRequest(
                url='https://example.com/large_file.bin',
                streaming_config=streaming_config
            )
            
            async with StreamingWebFetcher() as fetcher:
                result = await fetcher.stream_fetch(request)
            
            assert not result.is_success
            assert "exceeds limit" in result.error
    
    @pytest.mark.asyncio
    async def test_stream_fetch_without_content_length(self):
        """Test streaming without Content-Length header."""
        test_data = b"Unknown size content"
        
        with aioresponses() as m:
            m.get(
                'https://example.com/unknown_size.txt',
                body=test_data,
                status=200
                # No Content-Length header
            )
            
            request = StreamRequest(url='https://example.com/unknown_size.txt')
            
            async with StreamingWebFetcher() as fetcher:
                result = await fetcher.stream_fetch(request)
            
            assert result.is_success
            assert result.bytes_downloaded == len(test_data)
            assert result.total_bytes is None  # Unknown size


class TestDownloadFileFunction:
    """Test the download_file convenience function."""
    
    @pytest.mark.asyncio
    async def test_download_file_success(self):
        """Test successful file download."""
        test_data = b"File download test content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "downloaded_file.txt"
            
            with aioresponses() as m:
                m.get(
                    'https://example.com/download.txt',
                    body=test_data,
                    status=200,
                    headers={'Content-Length': str(len(test_data))}
                )
                
                result = await download_file(
                    url='https://example.com/download.txt',
                    output_path=output_path,
                    chunk_size=1024
                )
                
                assert result.is_success
                assert result.output_path == output_path
                assert output_path.exists()
                assert output_path.read_bytes() == test_data
    
    @pytest.mark.asyncio
    async def test_download_file_with_progress(self):
        """Test file download with progress callback."""
        test_data = b"x" * 5000  # 5KB
        progress_calls = []
        
        def progress_callback(progress: ProgressInfo):
            progress_calls.append(progress)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "progress_test.bin"
            
            with aioresponses() as m:
                m.get(
                    'https://example.com/progress_test.bin',
                    body=test_data,
                    status=200,
                    headers={'Content-Length': str(len(test_data))}
                )
                
                result = await download_file(
                    url='https://example.com/progress_test.bin',
                    output_path=output_path,
                    chunk_size=1024,
                    progress_callback=progress_callback
                )
                
                assert result.is_success
                assert len(progress_calls) > 0
                assert output_path.exists()
