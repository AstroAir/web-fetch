#!/usr/bin/env python3
"""
Testing examples for applications using the web-fetch library.

This script demonstrates various testing patterns including:
- Unit testing with mocking
- Integration testing
- Performance testing
- Error scenario testing
- Test fixtures and utilities
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from typing import Dict, List, Any, AsyncGenerator
from datetime import datetime

from web_fetch import (
    WebFetcher,
    FetchConfig,
    FetchRequest,
    FetchResult,
    ContentType,
    fetch_url,
    WebFetchError,
    HTTPError,
    TimeoutError,
)


class TestWebFetchBasics(unittest.TestCase):
    """Basic unit tests for web-fetch functionality."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.config = FetchConfig(
            total_timeout=10.0,
            max_retries=2,
            max_concurrent_requests=5
        )
    
    def test_config_creation(self) -> None:
        """Test configuration creation and validation."""
        config = FetchConfig(
            total_timeout=30.0,
            max_retries=3,
            max_concurrent_requests=10
        )
        
        self.assertEqual(config.total_timeout, 30.0)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.max_concurrent_requests, 10)
    
    def test_request_creation(self) -> None:
        """Test request creation with different parameters."""
        # Basic request
        request = FetchRequest(url="https://example.com")
        self.assertEqual(str(request.url), "https://example.com")
        self.assertEqual(request.method, "GET")
        
        # POST request with data
        post_request = FetchRequest(
            url="https://example.com/api",
            method="POST",
            data=json.dumps({"key": "value"}),
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(post_request.method, "POST")
        self.assertIn("Content-Type", post_request.headers)


class TestWebFetchMocking(unittest.TestCase):
    """Test web-fetch with mocked responses."""
    
    @patch('web_fetch.WebFetcher.fetch_single')
    async def test_mocked_successful_response(self, mock_fetch: Any) -> None:
        """Test mocked successful response."""
        # Setup mock
        mock_result = FetchResult(
            url="https://example.com",
            status_code=200,
            content={"message": "success"},
            headers={"content-type": "application/json"},
            response_time=0.5
        )
        mock_fetch.return_value = mock_result
        
        # Test
        async with WebFetcher() as fetcher:
            request = FetchRequest(url="https://example.com")
            result = await fetcher.fetch_single(request)
            
            self.assertTrue(result.is_success)
            self.assertEqual(result.status_code, 200)
            self.assertIsInstance(result.content, dict)
            if isinstance(result.content, dict):
                self.assertEqual(result.content["message"], "success")
    
    @patch('web_fetch.WebFetcher.fetch_single')
    async def test_mocked_error_response(self, mock_fetch: Any) -> None:
        """Test mocked error response."""
        # Setup mock
        mock_result = FetchResult(
            url="https://example.com",
            status_code=404,
            content=None,
            headers={},
            response_time=0.2,
            error="Not Found"
        )
        mock_fetch.return_value = mock_result
        
        # Test
        async with WebFetcher() as fetcher:
            request = FetchRequest(url="https://example.com")
            result = await fetcher.fetch_single(request)
            
            self.assertFalse(result.is_success)
            self.assertEqual(result.status_code, 404)
            self.assertEqual(result.error, "Not Found")


class TestWebFetchIntegration(unittest.TestCase):
    """Integration tests with real HTTP endpoints."""
    
    async def test_real_http_get(self) -> None:
        """Test real HTTP GET request."""
        result = await fetch_url("https://httpbin.org/get", ContentType.JSON)
        
        self.assertTrue(result.is_success)
        self.assertEqual(result.status_code, 200)
        self.assertIsInstance(result.content, dict)
        if isinstance(result.content, dict):
            self.assertIn("url", result.content)
    
    async def test_real_http_post(self) -> None:
        """Test real HTTP POST request."""
        config = FetchConfig(total_timeout=15.0)
        
        async with WebFetcher(config) as fetcher:
            request = FetchRequest(
                url="https://httpbin.org/post",
                method="POST",
                content_type=ContentType.JSON,
                data=json.dumps({"test": "data"}),
                headers={"Content-Type": "application/json"}
            )
            
            result = await fetcher.fetch_single(request)
            
            self.assertTrue(result.is_success)
            self.assertEqual(result.status_code, 200)
            self.assertIsInstance(result.content, dict)
            if isinstance(result.content, dict):
                self.assertIn("json", result.content)
    
    async def test_error_handling(self) -> None:
        """Test error handling with real endpoints."""
        # Test 404
        result = await fetch_url("https://httpbin.org/status/404", ContentType.TEXT)
        self.assertFalse(result.is_success)
        self.assertEqual(result.status_code, 404)
        
        # Test 500
        result = await fetch_url("https://httpbin.org/status/500", ContentType.TEXT)
        self.assertFalse(result.is_success)
        self.assertEqual(result.status_code, 500)


class MockWebService:
    """Mock web service for testing."""
    
    def __init__(self) -> None:
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.call_count: Dict[str, int] = {}
    
    def add_response(self, url: str, response: Dict[str, Any]) -> None:
        """Add a mock response for a URL."""
        self.responses[url] = response
        self.call_count[url] = 0
    
    async def fetch(self, url: str) -> FetchResult:
        """Mock fetch method."""
        self.call_count[url] = self.call_count.get(url, 0) + 1
        
        if url in self.responses:
            response_data = self.responses[url]
            return FetchResult(
                url=url,
                status_code=response_data.get("status_code", 200),
                content=response_data.get("content"),
                headers=response_data.get("headers", {}),
                response_time=response_data.get("response_time", 0.1)
            )
        else:
            return FetchResult(
                url=url,
                status_code=404,
                content=None,
                headers={},
                response_time=0.1,
                error="Not Found"
            )


class TestApplicationWithWebFetch(unittest.TestCase):
    """Test an application that uses web-fetch."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_service = MockWebService()
    
    async def test_user_service_integration(self) -> None:
        """Test user service integration."""
        
        class UserService:
            """Example user service."""
            
            def __init__(self, fetcher: Any) -> None:
                self.fetcher = fetcher
                self.base_url = "https://api.example.com"
            
            async def get_user(self, user_id: int) -> Dict:
                """Get user by ID."""
                request = FetchRequest(
                    url=f"{self.base_url}/users/{user_id}",
                    content_type=ContentType.JSON
                )
                
                result = await self.fetcher.fetch_single(request)
                
                if result.is_success:
                    if isinstance(result.content, dict):
                        return result.content
                    else:
                        raise Exception("Expected dict response")
                else:
                    raise Exception(f"Failed to get user: {result.error}")
            
            async def create_user(self, user_data: Dict) -> Dict:
                """Create a new user."""
                request = FetchRequest(
                    url=f"{self.base_url}/users",
                    method="POST",
                    content_type=ContentType.JSON,
                    data=json.dumps(user_data),
                    headers={"Content-Type": "application/json"}
                )
                
                result = await self.fetcher.fetch_single(request)
                
                if result.is_success:
                    if isinstance(result.content, dict):
                        return result.content
                    else:
                        raise Exception("Expected dict response")
                else:
                    raise Exception(f"Failed to create user: {result.error}")
        
        # Setup mock responses
        self.mock_service.add_response(
            "https://api.example.com/users/1",
            {
                "status_code": 200,
                "content": {"id": 1, "name": "John Doe", "email": "john@example.com"}
            }
        )
        
        self.mock_service.add_response(
            "https://api.example.com/users",
            {
                "status_code": 201,
                "content": {"id": 2, "name": "Jane Doe", "email": "jane@example.com"}
            }
        )
        
        # Test with mock
        with patch('web_fetch.WebFetcher.fetch_single', side_effect=self.mock_service.fetch):
            async with WebFetcher() as fetcher:
                user_service = UserService(fetcher)
                
                # Test get user
                user = await user_service.get_user(1)
                self.assertEqual(user["name"], "John Doe")
                
                # Test create user
                new_user_data = {"name": "Jane Doe", "email": "jane@example.com"}
                created_user = await user_service.create_user(new_user_data)
                self.assertEqual(created_user["name"], "Jane Doe")


class TestPerformance(unittest.TestCase):
    """Performance tests for web-fetch."""
    
    async def test_concurrent_requests_performance(self) -> None:
        """Test performance of concurrent requests."""
        urls = [f"https://httpbin.org/delay/1" for _ in range(5)]
        
        start_time = datetime.now()
        
        config = FetchConfig(
            total_timeout=30.0,
            max_concurrent_requests=5
        )
        
        from web_fetch import fetch_urls
        batch_result = await fetch_urls(urls, ContentType.JSON, config)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete in roughly 1 second (not 5 seconds) due to concurrency
        self.assertLess(duration, 3.0, "Concurrent requests should be faster than sequential")
        self.assertEqual(batch_result.successful_requests, 5)
    
    async def test_memory_usage_with_large_responses(self) -> None:
        """Test memory usage with large responses."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Fetch a large response
        result = await fetch_url("https://httpbin.org/bytes/1048576", ContentType.RAW)  # 1MB
        
        self.assertTrue(result.is_success)
        if result.content is not None:
            self.assertGreaterEqual(len(result.content), 1048576)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 10MB for 1MB response)
        self.assertLess(memory_increase, 10 * 1024 * 1024)


class TestErrorScenarios(unittest.TestCase):
    """Test various error scenarios."""
    
    async def test_timeout_scenarios(self) -> None:
        """Test different timeout scenarios."""
        # Very short timeout should fail
        config = FetchConfig(total_timeout=0.1)
        
        result = await fetch_url("https://httpbin.org/delay/2", ContentType.TEXT, config)
        self.assertFalse(result.is_success)
    
    async def test_invalid_url_handling(self) -> None:
        """Test handling of invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "http://",
            "https://invalid-domain-12345.com",
            "",
        ]
        
        for url in invalid_urls:
            try:
                result = await fetch_url(url, ContentType.TEXT)
                # If it doesn't raise an exception, it should at least fail
                self.assertFalse(result.is_success)
            except Exception:
                # Exception is also acceptable for invalid URLs
                pass
    
    async def test_retry_behavior(self) -> None:
        """Test retry behavior with failing endpoints."""
        config = FetchConfig(
            max_retries=3,
            retry_delay=0.1,  # Fast retries for testing
            total_timeout=10.0
        )
        
        start_time = datetime.now()
        result = await fetch_url("https://httpbin.org/status/500", ContentType.TEXT, config)
        end_time = datetime.now()
        
        # Should fail after retries
        self.assertFalse(result.is_success)
        
        # Should have taken some time due to retries
        duration = (end_time - start_time).total_seconds()
        self.assertGreater(duration, 0.3)  # At least 3 retries * 0.1s delay


# Pytest-style tests
@pytest.mark.asyncio
async def test_fetch_url_success() -> None:
    """Test successful URL fetch with pytest."""
    result = await fetch_url("https://httpbin.org/get", ContentType.JSON)
    
    assert result.is_success
    assert result.status_code == 200
    assert isinstance(result.content, dict)
    assert "url" in result.content


@pytest.mark.asyncio
async def test_fetch_url_failure() -> None:
    """Test failed URL fetch with pytest."""
    result = await fetch_url("https://httpbin.org/status/404", ContentType.TEXT)
    
    assert not result.is_success
    assert result.status_code == 404


@pytest.fixture
async def web_fetcher() -> AsyncGenerator[Any, None]:
    """Pytest fixture for WebFetcher."""
    config = FetchConfig(total_timeout=10.0, max_retries=2)
    async with WebFetcher(config) as fetcher:
        yield fetcher


@pytest.mark.asyncio
async def test_with_fixture(web_fetcher: Any) -> None:
    """Test using pytest fixture."""
    request = FetchRequest(url="https://httpbin.org/get", content_type=ContentType.JSON)
    result = await web_fetcher.fetch_single(request)
    
    assert result.is_success
    assert result.status_code == 200


def run_unittest_examples() -> None:
    """Run unittest examples."""
    print("=== Running unittest examples ===\n")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(TestWebFetchBasics('test_config_creation'))
    suite.addTest(TestWebFetchBasics('test_request_creation'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")


async def run_async_tests() -> None:
    """Run async test examples."""
    print("=== Running async test examples ===\n")
    
    # Integration tests
    test_integration = TestWebFetchIntegration()
    
    try:
        await test_integration.test_real_http_get()
        print("✅ Real HTTP GET test passed")
    except Exception as e:
        print(f"❌ Real HTTP GET test failed: {e}")
    
    try:
        await test_integration.test_real_http_post()
        print("✅ Real HTTP POST test passed")
    except Exception as e:
        print(f"❌ Real HTTP POST test failed: {e}")
    
    try:
        await test_integration.test_error_handling()
        print("✅ Error handling test passed")
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
    
    # Performance tests
    test_performance = TestPerformance()
    
    try:
        await test_performance.test_concurrent_requests_performance()
        print("✅ Concurrent requests performance test passed")
    except Exception as e:
        print(f"❌ Concurrent requests performance test failed: {e}")


async def main() -> None:
    """Run all testing examples."""
    print("Web Fetch Library - Testing Examples")
    print("=" * 50)
    print()
    
    # Run unittest examples
    run_unittest_examples()
    
    print()
    
    # Run async tests
    await run_async_tests()
    
    print("\n🎉 Testing examples completed!")
    print("\nTesting Best Practices Demonstrated:")
    print("- Unit testing with mocking")
    print("- Integration testing with real endpoints")
    print("- Performance testing")
    print("- Error scenario testing")
    print("- Pytest fixtures and async tests")
    print("- Mock services for isolated testing")


if __name__ == "__main__":
    asyncio.run(main())
