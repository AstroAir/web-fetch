"""
Comprehensive unit tests for core fetcher functionality.

This module contains extensive tests for WebFetcher and StreamingWebFetcher classes,
covering edge cases, error conditions, and integration points that aren't covered
in the basic test suite.
"""

import asyncio
import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta

import aiohttp
from aioresponses import aioresponses

# Import directly to avoid main package import issues
from web_fetch.src.core_fetcher import WebFetcher
from web_fetch.src.streaming_fetcher import StreamingWebFetcher
from web_fetch.models.http import (
    FetchConfig, FetchRequest, BatchFetchRequest,
    StreamingConfig, StreamRequest
)
from web_fetch.models.base import ContentType, ProgressInfo, RequestHeaders
from web_fetch.exceptions import (
    WebFetchError, HTTPError, ConnectionError, TimeoutError, ContentError
)


class TestWebFetcherComprehensive:
    """Comprehensive tests for WebFetcher class."""
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_comprehensive(self):
        """Test comprehensive session lifecycle management."""
        headers = RequestHeaders(user_agent="TestAgent/1.0")
        config = FetchConfig(
            total_timeout=30.0,
            max_concurrent_requests=10,
            verify_ssl=True,
            headers=headers
        )
        
        fetcher = WebFetcher(config)
        
        # Initially no session
        assert fetcher._session is None
        assert fetcher._semaphore is None
        
        # Create session manually
        await fetcher._create_session()
        assert fetcher._session is not None
        assert fetcher._semaphore is not None
        assert fetcher._semaphore._value == 10
        
        # Session should have correct configuration
        session = fetcher._session
        assert session._timeout.total == 30.0
        # Check SSL verification through connector
        connector = session._connector
        assert hasattr(connector, '_ssl') or hasattr(connector, '_verify_ssl')
        
        # Close session
        await fetcher.close()
        assert fetcher._session is None
        assert fetcher._semaphore is None
        
        # Double close should be safe
        await fetcher.close()
    
    @pytest.mark.asyncio
    async def test_lazy_session_initialization_comprehensive(self):
        """Test comprehensive lazy session initialization."""
        fetcher = WebFetcher()
        
        with aioresponses() as m:
            m.get('https://example.com', payload={'test': True}, status=200)
            
            request = FetchRequest(
                url='https://example.com',
                content_type=ContentType.JSON
            )
            
            # Session should be created automatically
            result = await fetcher.fetch_single(request)
            
            assert fetcher._session is not None
            assert result.is_success
            
        await fetcher.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self):
        """Test concurrent request limiting with semaphore."""
        config = FetchConfig(max_concurrent_requests=2)
        
        with aioresponses() as m:
            # Add multiple URLs with delays to test concurrency
            for i in range(5):
                m.get(f'https://example.com/{i}', payload={'id': i}, status=200)
            
            requests = [
                FetchRequest(url=f'https://example.com/{i}', content_type=ContentType.JSON)
                for i in range(5)
            ]
            
            batch_request = BatchFetchRequest(requests=requests)
            
            async with WebFetcher(config) as fetcher:
                # Track concurrent requests
                original_fetch = fetcher._fetch_single_with_retries
                concurrent_count = 0
                max_concurrent = 0
                
                async def track_concurrent(*args, **kwargs):
                    nonlocal concurrent_count, max_concurrent
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)
                    try:
                        return await original_fetch(*args, **kwargs)
                    finally:
                        concurrent_count -= 1
                
                fetcher._fetch_single_with_retries = track_concurrent
                
                result = await fetcher.fetch_batch(batch_request)
                
                assert result.successful_requests == 5
                assert max_concurrent <= 2  # Should not exceed semaphore limit
    
    @pytest.mark.asyncio
    async def test_retry_logic_comprehensive(self):
        """Test comprehensive retry logic with different scenarios."""
        config = FetchConfig(
            max_retries=3,
            retry_delay=0.01,  # Fast for testing
            retry_backoff_factor=2.0
        )
        
        # Test exponential backoff
        with aioresponses() as m:
            # Fail 3 times, then succeed
            m.get('https://example.com', status=500)
            m.get('https://example.com', status=502)
            m.get('https://example.com', status=503)
            m.get('https://example.com', payload={'success': True}, status=200)
            
            request = FetchRequest(
                url='https://example.com',
                content_type=ContentType.JSON
            )
            
            start_time = time.time()
            
            async with WebFetcher(config) as fetcher:
                result = await fetcher.fetch_single(request)
            
            elapsed = time.time() - start_time
            
            assert result.is_success
            assert result.retry_count == 3
            # Should have delays: 0.01, 0.02, 0.04 = ~0.07 seconds minimum
            assert elapsed >= 0.05
    
    @pytest.mark.asyncio
    async def test_retry_on_specific_errors(self):
        """Test retry behavior on specific error types."""
        config = FetchConfig(max_retries=2, retry_delay=0.01)
        
        # Test retry on server errors (5xx)
        with aioresponses() as m:
            m.get('https://example.com/server-error', status=500)
            m.get('https://example.com/server-error', status=500)
            m.get('https://example.com/server-error', payload={'recovered': True}, status=200)
            
            request = FetchRequest(
                url='https://example.com/server-error',
                content_type=ContentType.JSON
            )
            
            async with WebFetcher(config) as fetcher:
                result = await fetcher.fetch_single(request)
            
            assert result.is_success
            assert result.retry_count == 2
        
        # Test no retry on client errors (4xx)
        with aioresponses() as m:
            m.get('https://example.com/not-found', status=404)
            
            request = FetchRequest(url='https://example.com/not-found')
            
            async with WebFetcher(config) as fetcher:
                result = await fetcher.fetch_single(request)
            
            assert not result.is_success
            assert result.status_code == 404
            assert result.retry_count == 0  # No retries for 4xx
    
    @pytest.mark.asyncio
    async def test_content_parsing_edge_cases(self):
        """Test content parsing edge cases and error conditions."""
        async with WebFetcher() as fetcher:
            # Test empty content
            empty_result = await fetcher._parse_content(b'', ContentType.JSON)
            assert empty_result is None
            
            # Test malformed JSON
            with pytest.raises(ContentError, match="Failed to parse JSON"):
                await fetcher._parse_content(b'{"invalid": json}', ContentType.JSON)
            
            # Test malformed HTML
            malformed_html = b'<html><head><title>Test</head><body>No closing tags'
            html_result = await fetcher._parse_content(malformed_html, ContentType.HTML)
            assert isinstance(html_result, dict)
            assert html_result['title'] == 'Test'
            
            # Test binary content as text (should handle encoding errors)
            binary_content = b'\x00\x01\x02\x03\xff\xfe\xfd\xfc'
            text_result = await fetcher._parse_content(binary_content, ContentType.TEXT)
            # Should handle encoding errors gracefully
            assert isinstance(text_result, str)
            
            # Test very large JSON
            large_json = json.dumps({'data': 'x' * 10000}).encode()
            json_result = await fetcher._parse_content(large_json, ContentType.JSON)
            assert json_result['data'] == 'x' * 10000
    
    @pytest.mark.asyncio
    async def test_request_preparation_comprehensive(self):
        """Test comprehensive request preparation with various options."""
        headers = RequestHeaders(
            user_agent='TestBot/1.0',
            custom_headers={}
        )
        config = FetchConfig(
            headers=headers,
            verify_ssl=False
        )
        
        async with WebFetcher(config) as fetcher:
            # Test with all request options
            request = FetchRequest(
                url='https://api.example.com/data',
                method='POST',
                headers={'Authorization': 'Bearer token123', 'Content-Type': 'application/json'},
                data={'key': 'value'},
                params={'filter': 'active', 'limit': '10'},
                timeout_override=15.0,
                content_type=ContentType.JSON
            )
            
            # Mock the session to capture the prepared request
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.read.return_value = b'{"result": "success"}'
            mock_session.request.return_value.__aenter__.return_value = mock_response
            
            fetcher._session = mock_session
            
            result = await fetcher.fetch_single(request)
            
            # Verify the request was prepared correctly
            mock_session.request.assert_called_once()
            call_args = mock_session.request.call_args
            
            assert call_args[0][0] == 'POST'  # method
            assert 'api.example.com' in call_args[0][1]  # URL
            assert 'filter=active' in call_args[0][1]  # params
            assert 'limit=10' in call_args[0][1]
            
            # Check headers
            headers = call_args[1]['headers']
            assert headers['Authorization'] == 'Bearer token123'
            assert headers['User-Agent'] == 'TestBot/1.0'  # From config
            
            # Check timeout
            timeout = call_args[1]['timeout']
            assert timeout.total == 15.0
    
    @pytest.mark.asyncio
    async def test_response_size_limit_comprehensive(self):
        """Test comprehensive response size limit enforcement."""
        config = FetchConfig(max_response_size=1024)  # 1KB limit
        
        async with WebFetcher(config) as fetcher:
            # Test content within limit
            small_content = b'x' * 512
            result = await fetcher._parse_content(small_content, ContentType.TEXT)
            assert len(result) == 512
            
            # Test content exceeding limit
            large_content = b'x' * 2048  # 2KB, exceeds limit
            
            with pytest.raises(ContentError, match="Response size .* exceeds maximum"):
                await fetcher._validate_response_size(large_content)
    
    @pytest.mark.asyncio
    async def test_batch_processing_comprehensive(self):
        """Test comprehensive batch processing with mixed results."""
        with aioresponses() as m:
            # Mix of successful and failed requests
            m.get('https://example.com/success1', payload={'id': 1}, status=200)
            m.get('https://example.com/success2', payload={'id': 2}, status=200)
            m.get('https://example.com/notfound', status=404)
            m.get('https://example.com/error', status=500)
            m.get('https://example.com/timeout', exception=asyncio.TimeoutError())
            
            requests = [
                FetchRequest(url='https://example.com/success1', content_type=ContentType.JSON),
                FetchRequest(url='https://example.com/success2', content_type=ContentType.JSON),
                FetchRequest(url='https://example.com/notfound', content_type=ContentType.JSON),
                FetchRequest(url='https://example.com/error', content_type=ContentType.JSON),
                FetchRequest(url='https://example.com/timeout', content_type=ContentType.JSON),
            ]
            
            batch_request = BatchFetchRequest(
                requests=requests,
                fail_fast=False,
                max_concurrent=3
            )
            
            async with WebFetcher() as fetcher:
                result = await fetcher.fetch_batch(batch_request)
            
            assert result.total_requests == 5
            assert result.successful_requests == 2
            assert result.failed_requests == 3
            assert result.success_rate == 40.0
            
            # Check individual results
            successful_results = [r for r in result.results if r.is_success]
            failed_results = [r for r in result.results if not r.is_success]
            
            assert len(successful_results) == 2
            assert len(failed_results) == 3
            
            # Check error types
            status_codes = [r.status_code for r in failed_results if r.status_code]
            assert 404 in status_codes
            assert 500 in status_codes


class TestStreamingWebFetcherComprehensive:
    """Comprehensive tests for StreamingWebFetcher class."""

    @pytest.mark.asyncio
    async def test_streaming_download_comprehensive(self):
        """Test comprehensive streaming download functionality."""
        config = StreamingConfig(
            chunk_size=1024,
            buffer_size=4096,
            enable_progress=True,
            progress_interval=0.01
        )

        # Create test data
        test_data = b'x' * 10240  # 10KB of data

        with aioresponses() as m:
            m.get('https://example.com/large-file', body=test_data, status=200)

            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                request = StreamRequest(
                    url='https://example.com/large-file',
                    output_path=tmp_path
                )

                progress_updates = []

                def progress_callback(progress: ProgressInfo):
                    progress_updates.append(progress)

                async with StreamingWebFetcher(config) as fetcher:
                    result = await fetcher.stream_download(request, progress_callback)

                assert result.is_success
                assert result.bytes_downloaded == 10240
                assert tmp_path.read_bytes() == test_data

                # Should have received progress updates
                assert len(progress_updates) > 0
                assert progress_updates[-1].downloaded_bytes == 10240
                assert progress_updates[-1].percentage == 100.0

            finally:
                tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_streaming_with_resume_comprehensive(self):
        """Test comprehensive streaming with resume functionality."""
        config = StreamingConfig(chunk_size=1024, enable_resume=True)

        # Create test data
        full_data = b'0123456789' * 1000  # 10KB
        partial_data = full_data[:5000]   # First 5KB
        remaining_data = full_data[5000:] # Last 5KB

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            # Write partial data to simulate interrupted download
            tmp_path.write_bytes(partial_data)

        try:
            with aioresponses() as m:
                # Mock server supporting range requests
                m.get(
                    'https://example.com/resumable-file',
                    body=remaining_data,
                    status=206,  # Partial Content
                    headers={
                        'Content-Range': 'bytes 5000-9999/10000',
                        'Content-Length': '5000'
                    }
                )

                request = StreamRequest(
                    url='https://example.com/resumable-file',
                    output_path=tmp_path
                )

                async with StreamingWebFetcher(config) as fetcher:
                    result = await fetcher.stream_download(request)

                assert result.is_success
                assert result.bytes_downloaded == 5000  # Only downloaded remaining part
                assert tmp_path.read_bytes() == full_data  # Complete file

        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_streaming_error_conditions(self):
        """Test streaming error conditions and recovery."""
        config = StreamingConfig(chunk_size=1024, max_file_size=5000)

        # Test file size limit exceeded
        large_data = b'x' * 10000  # 10KB, exceeds 5KB limit

        with aioresponses() as m:
            m.get(
                'https://example.com/too-large',
                body=large_data,
                status=200,
                headers={'Content-Length': '10000'}
            )

            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                request = StreamRequest(
                    url='https://example.com/too-large',
                    output_path=tmp_path
                )

                async with StreamingWebFetcher(config) as fetcher:
                    result = await fetcher.stream_download(request)

                assert not result.is_success
                assert "exceeds maximum file size" in str(result.error)

            finally:
                tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_streaming_progress_tracking_comprehensive(self):
        """Test comprehensive progress tracking during streaming."""
        config = StreamingConfig(
            chunk_size=1000,
            enable_progress=True,
            progress_interval=0.001  # Very frequent updates for testing
        )

        test_data = b'x' * 5000  # 5KB

        with aioresponses() as m:
            m.get(
                'https://example.com/progress-test',
                body=test_data,
                status=200,
                headers={'Content-Length': '5000'}
            )

            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                request = StreamRequest(
                    url='https://example.com/progress-test',
                    output_path=tmp_path
                )

                progress_updates = []

                def detailed_progress_callback(progress: ProgressInfo):
                    progress_updates.append({
                        'bytes_downloaded': progress.downloaded_bytes,
                        'total_bytes': progress.total_bytes,
                        'progress_percent': progress.percentage,
                        'download_speed': progress.speed_bytes_per_second,
                        'eta_seconds': progress.eta_seconds
                    })

                async with StreamingWebFetcher(config) as fetcher:
                    result = await fetcher.stream_download(request, detailed_progress_callback)

                assert result.is_success
                assert len(progress_updates) >= 2  # Should have multiple updates

                # Check progress progression
                first_update = progress_updates[0]
                last_update = progress_updates[-1]

                assert first_update['bytes_downloaded'] < last_update['bytes_downloaded']
                assert last_update['bytes_downloaded'] == 5000
                assert last_update['progress_percent'] == 100.0
                assert last_update['total_bytes'] == 5000

                # Check that download speed was calculated
                assert any(update['download_speed'] > 0 for update in progress_updates)

            finally:
                tmp_path.unlink(missing_ok=True)


class TestErrorHandlingComprehensive:
    """Comprehensive tests for error handling across all fetcher types."""

    @pytest.mark.asyncio
    async def test_network_error_scenarios(self):
        """Test various network error scenarios."""
        async with WebFetcher() as fetcher:
            # Test DNS resolution failure
            request = FetchRequest(url='https://non-existent-domain-12345.invalid')
            result = await fetcher.fetch_single(request)

            assert not result.is_success
            assert result.error is not None
            assert isinstance(result.error, (ConnectionError, aiohttp.ClientError))

    @pytest.mark.asyncio
    async def test_timeout_scenarios_comprehensive(self):
        """Test comprehensive timeout scenarios."""
        config = FetchConfig(total_timeout=0.1)  # Very short timeout

        with aioresponses() as m:
            # Simulate slow response
            async def slow_callback(url, **kwargs):
                await asyncio.sleep(0.2)  # Longer than timeout
                return aioresponses.CallbackResult(status=200, payload={'data': 'test'})

            m.get('https://example.com/slow', callback=slow_callback)

            request = FetchRequest(
                url='https://example.com/slow',
                content_type=ContentType.JSON
            )

            async with WebFetcher(config) as fetcher:
                result = await fetcher.fetch_single(request)

            assert not result.is_success
            assert result.error is not None
            # Should be a timeout-related error
            assert any(word in str(result.error).lower() for word in ['timeout', 'time'])

    @pytest.mark.asyncio
    async def test_ssl_verification_errors(self):
        """Test SSL verification error handling."""
        config = FetchConfig(verify_ssl=True)

        # This would normally require a server with invalid SSL
        # For testing, we'll simulate the error condition
        async with WebFetcher(config) as fetcher:
            with patch.object(fetcher._session, 'request') as mock_request:
                mock_request.side_effect = aiohttp.ClientSSLError("SSL verification failed")

                request = FetchRequest(url='https://invalid-ssl.example.com')
                result = await fetcher.fetch_single(request)

                assert not result.is_success
                assert "SSL" in str(result.error)

    @pytest.mark.asyncio
    async def test_content_encoding_errors(self):
        """Test content encoding error handling."""
        async with WebFetcher() as fetcher:
            # Test invalid UTF-8 content
            invalid_utf8 = b'\xff\xfe\x00\x01\x02\x03'

            # Should handle encoding errors gracefully
            result = await fetcher._parse_content(invalid_utf8, ContentType.TEXT)
            assert isinstance(result, str)  # Should still return a string

            # Test with different encoding
            latin1_content = "Café".encode('latin1')
            result = await fetcher._parse_content(latin1_content, ContentType.TEXT)
            assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
