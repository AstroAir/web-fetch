"""
Comprehensive tests for the streaming fetcher.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator

from web_fetch.streaming_fetcher import (
    StreamingFetcher,
    StreamingConfig,
    StreamChunk,
    StreamingResult,
    StreamingError,
)
from web_fetch.models import FetchConfig, ContentType
from web_fetch.exceptions import HTTPError, NetworkError, TimeoutError


class TestStreamingConfig:
    """Test streaming configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StreamingConfig()
        
        assert config.chunk_size == 8192
        assert config.max_chunks is None
        assert config.timeout_per_chunk == 10.0
        assert config.buffer_size == 1024 * 1024  # 1MB
        assert config.enable_compression is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = StreamingConfig(
            chunk_size=4096,
            max_chunks=100,
            timeout_per_chunk=5.0,
            buffer_size=512 * 1024,
            enable_compression=False
        )
        
        assert config.chunk_size == 4096
        assert config.max_chunks == 100
        assert config.timeout_per_chunk == 5.0
        assert config.buffer_size == 512 * 1024
        assert config.enable_compression is False
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid chunk size
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            StreamingConfig(chunk_size=0)
        
        # Invalid timeout
        with pytest.raises(ValueError, match="timeout_per_chunk must be positive"):
            StreamingConfig(timeout_per_chunk=0)
        
        # Invalid buffer size
        with pytest.raises(ValueError, match="buffer_size must be positive"):
            StreamingConfig(buffer_size=0)


class TestStreamChunk:
    """Test stream chunk model."""
    
    def test_chunk_creation(self):
        """Test stream chunk creation."""
        data = b"chunk data"
        chunk = StreamChunk(
            data=data,
            chunk_number=1,
            total_size=100,
            is_final=False
        )
        
        assert chunk.data == data
        assert chunk.chunk_number == 1
        assert chunk.size == len(data)
        assert chunk.total_size == 100
        assert chunk.is_final is False
    
    def test_final_chunk(self):
        """Test final chunk properties."""
        chunk = StreamChunk(
            data=b"final chunk",
            chunk_number=5,
            is_final=True
        )
        
        assert chunk.is_final is True
        assert chunk.chunk_number == 5
    
    def test_chunk_progress(self):
        """Test chunk progress calculation."""
        chunk = StreamChunk(
            data=b"data",
            chunk_number=3,
            total_size=100
        )
        
        # Progress calculation: (chunk_number * chunk_size) / total_size
        progress = chunk.get_progress()
        assert 0 <= progress <= 1


class TestStreamingResult:
    """Test streaming result model."""
    
    def test_result_creation(self):
        """Test streaming result creation."""
        chunks = [
            StreamChunk(b"chunk1", 1, 20, False),
            StreamChunk(b"chunk2", 2, 20, True)
        ]
        
        result = StreamingResult(
            url="https://example.com/stream",
            chunks=chunks,
            total_size=20,
            content_type=ContentType.BINARY
        )
        
        assert result.url == "https://example.com/stream"
        assert len(result.chunks) == 2
        assert result.total_size == 20
        assert result.content_type == ContentType.BINARY
    
    def test_get_complete_data(self):
        """Test getting complete data from chunks."""
        chunks = [
            StreamChunk(b"Hello, ", 1, 13, False),
            StreamChunk(b"World!", 2, 13, True)
        ]
        
        result = StreamingResult(
            url="https://example.com/stream",
            chunks=chunks,
            total_size=13
        )
        
        complete_data = result.get_complete_data()
        assert complete_data == b"Hello, World!"
    
    def test_get_text_data(self):
        """Test getting text data from chunks."""
        chunks = [
            StreamChunk("Hello, ".encode('utf-8'), 1, 13, False),
            StreamChunk("World!".encode('utf-8'), 2, 13, True)
        ]
        
        result = StreamingResult(
            url="https://example.com/stream",
            chunks=chunks,
            total_size=13,
            content_type=ContentType.TEXT
        )
        
        text_data = result.get_text_data()
        assert text_data == "Hello, World!"
    
    def test_streaming_stats(self):
        """Test streaming statistics."""
        chunks = [
            StreamChunk(b"chunk1", 1, 20, False),
            StreamChunk(b"chunk2", 2, 20, True)
        ]
        
        result = StreamingResult(
            url="https://example.com/stream",
            chunks=chunks,
            total_size=20,
            streaming_time=2.5
        )
        
        stats = result.get_stats()
        
        assert stats["total_chunks"] == 2
        assert stats["total_size"] == 20
        assert stats["streaming_time"] == 2.5
        assert stats["average_chunk_size"] == 10.0  # 20 / 2
        assert "throughput_bps" in stats


class TestStreamingFetcher:
    """Test streaming fetcher functionality."""
    
    @pytest.fixture
    def streaming_config(self):
        """Create streaming configuration."""
        return StreamingConfig(chunk_size=1024, timeout_per_chunk=5.0)
    
    @pytest.fixture
    def fetch_config(self):
        """Create fetch configuration."""
        return FetchConfig(total_timeout=30.0, max_retries=2)
    
    @pytest.fixture
    def fetcher(self, streaming_config, fetch_config):
        """Create streaming fetcher."""
        return StreamingFetcher(streaming_config, fetch_config)
    
    def test_fetcher_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.streaming_config.chunk_size == 1024
        assert fetcher.fetch_config.total_timeout == 30.0
        assert fetcher._session is None
    
    @pytest.mark.asyncio
    async def test_stream_url_basic(self, fetcher):
        """Test basic URL streaming."""
        url = "https://example.com/large-file.bin"
        
        # Mock response with streaming content
        mock_chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        async def mock_stream_chunks():
            for i, chunk_data in enumerate(mock_chunks):
                yield StreamChunk(
                    data=chunk_data,
                    chunk_number=i + 1,
                    total_size=len(b"".join(mock_chunks)),
                    is_final=(i == len(mock_chunks) - 1)
                )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            chunks = []
            async for chunk in fetcher.stream_url(url):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks[0].data == b"chunk1"
            assert chunks[1].data == b"chunk2"
            assert chunks[2].data == b"chunk3"
            assert chunks[2].is_final is True
    
    @pytest.mark.asyncio
    async def test_stream_with_progress_callback(self, fetcher):
        """Test streaming with progress callback."""
        url = "https://example.com/file.bin"
        progress_calls = []
        
        def progress_callback(chunk: StreamChunk):
            progress_calls.append(chunk.chunk_number)
        
        mock_chunks = [b"data1", b"data2"]
        
        async def mock_stream_chunks():
            for i, chunk_data in enumerate(mock_chunks):
                yield StreamChunk(
                    data=chunk_data,
                    chunk_number=i + 1,
                    total_size=10,
                    is_final=(i == len(mock_chunks) - 1)
                )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            chunks = []
            async for chunk in fetcher.stream_url(url, progress_callback=progress_callback):
                chunks.append(chunk)
            
            assert len(chunks) == 2
            assert progress_calls == [1, 2]
    
    @pytest.mark.asyncio
    async def test_stream_with_max_chunks(self, fetcher):
        """Test streaming with maximum chunk limit."""
        fetcher.streaming_config.max_chunks = 2
        url = "https://example.com/file.bin"
        
        mock_chunks = [b"chunk1", b"chunk2", b"chunk3", b"chunk4"]
        
        async def mock_stream_chunks():
            for i, chunk_data in enumerate(mock_chunks):
                yield StreamChunk(
                    data=chunk_data,
                    chunk_number=i + 1,
                    total_size=20,
                    is_final=(i == len(mock_chunks) - 1)
                )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            chunks = []
            async for chunk in fetcher.stream_url(url):
                chunks.append(chunk)
            
            # Should stop after max_chunks
            assert len(chunks) == 2
            assert chunks[0].data == b"chunk1"
            assert chunks[1].data == b"chunk2"
    
    @pytest.mark.asyncio
    async def test_fetch_streaming_complete(self, fetcher):
        """Test fetching complete streaming result."""
        url = "https://example.com/file.txt"
        
        mock_chunks = [b"Hello, ", b"streaming ", b"world!"]
        
        async def mock_stream_chunks():
            for i, chunk_data in enumerate(mock_chunks):
                yield StreamChunk(
                    data=chunk_data,
                    chunk_number=i + 1,
                    total_size=len(b"".join(mock_chunks)),
                    is_final=(i == len(mock_chunks) - 1)
                )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            result = await fetcher.fetch_streaming(url)
            
            assert isinstance(result, StreamingResult)
            assert result.url == url
            assert len(result.chunks) == 3
            assert result.get_complete_data() == b"Hello, streaming world!"
    
    @pytest.mark.asyncio
    async def test_stream_with_timeout(self, fetcher):
        """Test streaming with chunk timeout."""
        fetcher.streaming_config.timeout_per_chunk = 0.1  # Very short timeout
        url = "https://slow.example.com/file.bin"
        
        async def slow_stream_chunks():
            yield StreamChunk(b"chunk1", 1, 10, False)
            await asyncio.sleep(0.2)  # Longer than timeout
            yield StreamChunk(b"chunk2", 2, 10, True)
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = slow_stream_chunks()
            
            with pytest.raises(TimeoutError):
                chunks = []
                async for chunk in fetcher.stream_url(url):
                    chunks.append(chunk)
    
    @pytest.mark.asyncio
    async def test_stream_error_handling(self, fetcher):
        """Test streaming error handling."""
        url = "https://error.example.com/file.bin"
        
        async def error_stream_chunks():
            yield StreamChunk(b"chunk1", 1, 10, False)
            raise NetworkError("Network error during streaming")
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = error_stream_chunks()
            
            with pytest.raises(StreamingError) as exc_info:
                chunks = []
                async for chunk in fetcher.stream_url(url):
                    chunks.append(chunk)
            
            assert "Network error during streaming" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_stream_with_compression(self, fetcher):
        """Test streaming with compression support."""
        fetcher.streaming_config.enable_compression = True
        url = "https://example.com/compressed.gz"
        
        # Mock compressed data
        import gzip
        original_data = b"This is compressed data that should be larger when uncompressed"
        compressed_data = gzip.compress(original_data)
        
        async def mock_stream_chunks():
            yield StreamChunk(
                data=compressed_data,
                chunk_number=1,
                total_size=len(compressed_data),
                is_final=True
            )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            # Mock decompression
            with patch.object(fetcher, '_decompress_chunk') as mock_decompress:
                mock_decompress.return_value = original_data
                
                chunks = []
                async for chunk in fetcher.stream_url(url):
                    chunks.append(chunk)
                
                assert len(chunks) == 1
                mock_decompress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_streaming(self, fetcher):
        """Test concurrent streaming of multiple URLs."""
        urls = [
            "https://example.com/file1.bin",
            "https://example.com/file2.bin",
            "https://example.com/file3.bin"
        ]
        
        async def mock_stream_for_url(url):
            file_num = url.split('file')[1].split('.')[0]
            yield StreamChunk(
                data=f"data{file_num}".encode(),
                chunk_number=1,
                total_size=5,
                is_final=True
            )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.side_effect = lambda url, **kwargs: mock_stream_for_url(url)
            
            results = await fetcher.stream_multiple(urls)
            
            assert len(results) == 3
            for i, result in enumerate(results, 1):
                assert result.url == f"https://example.com/file{i}.bin"
                assert len(result.chunks) == 1
                assert result.chunks[0].data == f"data{i}".encode()
    
    @pytest.mark.asyncio
    async def test_stream_to_file(self, fetcher):
        """Test streaming directly to file."""
        url = "https://example.com/download.bin"
        file_path = "/tmp/downloaded.bin"
        
        mock_chunks = [b"file", b"content", b"data"]
        
        async def mock_stream_chunks():
            for i, chunk_data in enumerate(mock_chunks):
                yield StreamChunk(
                    data=chunk_data,
                    chunk_number=i + 1,
                    total_size=len(b"".join(mock_chunks)),
                    is_final=(i == len(mock_chunks) - 1)
                )
        
        with patch.object(fetcher, '_stream_response') as mock_stream:
            mock_stream.return_value = mock_stream_chunks()
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await fetcher.stream_to_file(url, file_path)
                
                assert result.url == url
                assert len(result.chunks) == 3
                
                # Verify file was written
                assert mock_file.write.call_count == 3
                mock_file.write.assert_any_call(b"file")
                mock_file.write.assert_any_call(b"content")
                mock_file.write.assert_any_call(b"data")
    
    @pytest.mark.asyncio
    async def test_cleanup(self, fetcher):
        """Test fetcher cleanup."""
        # Create session
        await fetcher._get_session()
        assert fetcher._session is not None
        
        # Cleanup should close session
        await fetcher.cleanup()
        assert fetcher._session is None
