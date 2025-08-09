"""
Comprehensive tests for extended resource components.

This module tests the new resource components including RSS feeds,
authenticated APIs, database connections, and cloud storage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Any, Dict, Generator
from pydantic import AnyUrl, SecretStr

from web_fetch.components.rss_component import RSSComponent
from web_fetch.components.authenticated_api_component import AuthenticatedAPIComponent
from web_fetch.components.database_component import DatabaseComponent
from web_fetch.components.cloud_storage_component import CloudStorageComponent
from web_fetch.models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from web_fetch.models.extended_resources import (
    RSSConfig, AuthenticatedAPIConfig, DatabaseConfig, CloudStorageConfig,
    DatabaseType, CloudStorageProvider, DatabaseQuery, CloudStorageOperation
)


class TestRSSComponent:
    """Test RSS/Atom feed component."""
    
    @pytest.fixture
    def rss_component(self) -> RSSComponent:
        """Create RSS component for testing."""
        config = ResourceConfig(enable_cache=True)
        rss_config = RSSConfig(max_items=10, include_content=True)
        return RSSComponent(config, rss_config)

    @pytest.fixture
    def sample_rss_content(self) -> bytes:
        """Sample RSS feed content for testing."""
        return b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <description>A test RSS feed</description>
                <link>https://example.com</link>
                <item>
                    <title>Test Item 1</title>
                    <description>First test item</description>
                    <link>https://example.com/item1</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Test Item 2</title>
                    <description>Second test item</description>
                    <link>https://example.com/item2</link>
                    <pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
    
    @pytest.mark.asyncio
    async def test_rss_fetch_success(self, rss_component: RSSComponent, sample_rss_content: bytes) -> None:
        """Test successful RSS feed fetching."""
        # Mock WebFetcher
        with patch('web_fetch.components.rss_component.WebFetcher') as mock_fetcher:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.status_code = 200
            mock_result.headers = {"Content-Type": "application/rss+xml"}
            mock_result.content = sample_rss_content
            mock_result.response_time = 0.5
            
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_single = AsyncMock(return_value=mock_result)
            mock_fetcher.return_value.__aenter__ = AsyncMock(return_value=mock_fetcher_instance)
            mock_fetcher.return_value.__aexit__ = AsyncMock(return_value=None)
            
            request = ResourceRequest(
                uri=AnyUrl("https://example.com/feed.xml"),
                kind=ResourceKind.RSS
            )
            
            result = await rss_component.fetch(request)
            
            assert result.status_code == 200
            assert result.error is None
            assert isinstance(result.content, dict)
            assert result.content["title"] == "Test Feed"
            assert result.content["description"] == "A test RSS feed"
            assert len(result.content["items"]) == 2
            assert "feed_metadata" in result.metadata
            assert "feed_items" in result.metadata
    
    @pytest.mark.asyncio
    async def test_rss_validation(self, rss_component: RSSComponent) -> None:
        """Test RSS feed validation."""
        # Valid feed result
        valid_result = ResourceResult(
            url="https://example.com/feed.xml",
            status_code=200,
            content={
                "title": "Test Feed",
                "description": "A test feed",
                "items": [{"title": "Item 1"}]
            }
        )
        
        validated = await rss_component.validate(valid_result)
        assert validated.error is None
        assert validated.metadata["validation"]["is_valid_feed"] is True
        assert validated.metadata["validation"]["has_title"] is True
        assert validated.metadata["validation"]["has_items"] is True
    
    def test_rss_cache_key(self, rss_component: RSSComponent) -> None:
        """Test RSS cache key generation."""
        request = ResourceRequest(
            uri=AnyUrl("https://example.com/feed.xml"),
            kind=ResourceKind.RSS,
            headers={"User-Agent": "test"}
        )
        
        cache_key = rss_component.cache_key(request)
        assert cache_key is not None
        assert "rss" in cache_key
        assert "https://example.com/feed.xml" in cache_key


class TestAuthenticatedAPIComponent:
    """Test authenticated API component."""
    
    @pytest.fixture
    def api_component(self) -> AuthenticatedAPIComponent:
        """Create authenticated API component for testing."""
        config = ResourceConfig(enable_cache=True)
        api_config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": "test-key",
                "key_name": "X-API-Key",
                "location": "header"
            }
        )
        return AuthenticatedAPIComponent(config, api_config)
    
    @pytest.mark.asyncio
    async def test_api_authentication_setup(self, api_component: AuthenticatedAPIComponent) -> None:
        """Test authentication setup."""
        assert api_component._auth_method is not None
        assert api_component.auth_manager is not None
        assert "default" in api_component.auth_manager._auth_methods
    
    @pytest.mark.asyncio
    async def test_api_fetch_with_auth(self, api_component: AuthenticatedAPIComponent) -> None:
        """Test API fetch with authentication."""
        with patch.object(api_component, '_apply_authentication') as mock_auth:
            with patch('web_fetch.components.authenticated_api_component.HTTPResourceComponent.fetch') as mock_fetch:
                # Mock authentication
                mock_request = MagicMock()
                mock_auth.return_value = mock_request
                
                # Mock HTTP fetch
                mock_result = ResourceResult(
                    url="https://api.example.com/data",
                    status_code=200,
                    content={"data": "test"},
                    metadata={}
                )
                mock_fetch.return_value = mock_result
                
                request = ResourceRequest(
                    uri=AnyUrl("https://api.example.com/data"),
                    kind=ResourceKind.API_AUTH
                )
                
                result = await api_component.fetch(request)
                
                assert result.status_code == 200
                assert "authentication" in result.metadata
                assert result.metadata["authentication"]["authenticated"] is True
                mock_auth.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_auth_retry_on_failure(self, api_component: AuthenticatedAPIComponent) -> None:
        """Test authentication retry on 401/403 errors."""
        with patch.object(api_component, '_apply_authentication') as mock_auth:
            with patch('web_fetch.components.authenticated_api_component.HTTPResourceComponent.fetch') as mock_fetch:
                mock_request = MagicMock()
                mock_auth.return_value = mock_request
                
                # First call returns 401, second call succeeds
                mock_fetch.side_effect = [
                    ResourceResult(url="test", status_code=401, error="Unauthorized"),
                    ResourceResult(url="test", status_code=200, content={"data": "test"}, metadata={})
                ]
                
                request = ResourceRequest(
                    uri=AnyUrl("https://api.example.com/data"),
                    kind=ResourceKind.API_AUTH
                )
                
                result = await api_component.fetch(request)
                
                assert result.status_code == 200
                assert mock_auth.call_count == 2  # Called twice due to retry


class TestDatabaseComponent:
    """Test database component."""
    
    @pytest.fixture
    def db_component(self) -> DatabaseComponent:
        """Create database component for testing."""
        config = ResourceConfig(enable_cache=True)
        db_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password=SecretStr("password")
        )
        return DatabaseComponent(config, db_config)
    
    @pytest.mark.asyncio
    async def test_postgresql_query_execution(self, db_component: DatabaseComponent) -> None:
        """Test PostgreSQL query execution."""
        with patch('web_fetch.components.database_component.asyncpg') as mock_asyncpg:
            # Mock connection pool
            mock_pool = AsyncMock()
            mock_connection = AsyncMock()

            # Set up the connection pool acquire method properly
            mock_pool.acquire = AsyncMock(return_value=mock_connection)
            mock_pool.release = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Mock query result
            mock_connection.fetch.return_value = [
                {"id": 1, "name": "John"},
                {"id": 2, "name": "Jane"}
            ]
            
            request = ResourceRequest(
                uri=AnyUrl("postgresql://localhost:5432/test"),
                kind=ResourceKind.DATABASE,
                options={
                    "query": {
                        "query": "SELECT * FROM users",
                        "fetch_mode": "all"
                    }
                }
            )
            
            result = await db_component.fetch(request)
            
            assert result.status_code == 200
            assert result.error is None
            assert "data" in result.content
            assert len(result.content["data"]) == 2
            assert result.content["data"][0]["name"] == "John"
    
    def test_database_cache_key(self, db_component: DatabaseComponent) -> None:
        """Test database cache key generation."""
        request = ResourceRequest(
            uri=AnyUrl("postgresql://localhost:5432/test"),
            kind=ResourceKind.DATABASE,
            options={"query": {"query": "SELECT * FROM users"}}
        )
        
        cache_key = db_component.cache_key(request)
        assert cache_key is not None
        assert "database" in cache_key
        assert "postgresql" in cache_key


class TestCloudStorageComponent:
    """Test cloud storage component."""
    
    @pytest.fixture
    def storage_component(self) -> CloudStorageComponent:
        """Create cloud storage component for testing."""
        config = ResourceConfig(enable_cache=True)
        storage_config = CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key=SecretStr("access-key"),
            secret_key=SecretStr("secret-key"),
            region="us-east-1"
        )
        return CloudStorageComponent(config, storage_config)
    
    @pytest.mark.asyncio
    async def test_s3_list_operation(self, storage_component: CloudStorageComponent) -> None:
        """Test S3 list operation."""
        with patch('web_fetch.components.cloud_storage_component.boto3') as mock_boto3:
            # Mock S3 client
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session

            # Mock list response
            mock_client.list_objects_v2.return_value = {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 1024,
                        "LastModified": datetime(2024, 1, 1),
                        "ETag": "etag1"
                    },
                    {
                        "Key": "file2.txt",
                        "Size": 2048,
                        "LastModified": datetime(2024, 1, 2),
                        "ETag": "etag2"
                    }
                ]
            }
            
            request = ResourceRequest(
                uri=AnyUrl("s3://test-bucket"),
                kind=ResourceKind.CLOUD_STORAGE,
                options={
                    "operation": {
                        "operation": "list",
                        "prefix": "documents/"
                    }
                }
            )
            
            result = await storage_component.fetch(request)
            
            assert result.status_code == 200
            assert result.error is None
            assert result.content["operation"] == "list"
            assert len(result.content["objects"]) == 2
            assert result.content["objects"][0]["key"] == "file1.txt"
    
    def test_storage_cache_key(self, storage_component: CloudStorageComponent) -> None:
        """Test cloud storage cache key generation."""
        request = ResourceRequest(
            uri=AnyUrl("s3://test-bucket"),
            kind=ResourceKind.CLOUD_STORAGE,
            options={
                "operation": {
                    "operation": "get",
                    "key": "file.txt"
                }
            }
        )
        
        cache_key = storage_component.cache_key(request)
        assert cache_key is not None
        assert "cloud_storage" in cache_key
        assert "aws_s3" in cache_key


class TestExtendedComponentsErrorHandling:
    """Test error handling for extended components."""

    @pytest.mark.asyncio
    async def test_rss_invalid_feed_content(self) -> None:
        """Test RSS component with invalid feed content."""
        component = RSSComponent()

        with patch('web_fetch.components.rss_component.WebFetcher') as mock_fetcher:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.status_code = 200
            mock_result.content = b"Invalid XML content"
            mock_result.response_time = 0.5

            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_single = AsyncMock(return_value=mock_result)
            mock_fetcher.return_value.__aenter__ = AsyncMock(return_value=mock_fetcher_instance)
            mock_fetcher.return_value.__aexit__ = AsyncMock(return_value=None)

            request = ResourceRequest(
                uri=AnyUrl("https://example.com/invalid-feed.xml"),
                kind=ResourceKind.RSS
            )

            result = await component.fetch(request)
            assert result.error is not None
            assert "RSS feed fetch error" in result.error

    @pytest.mark.asyncio
    async def test_api_authentication_failure(self) -> None:
        """Test API component with authentication failure."""
        api_config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": "",  # Empty API key should fail
                "key_name": "X-API-Key",
                "location": "header"
            }
        )

        component = AuthenticatedAPIComponent(api_config=api_config)

        # Mock a failed authentication response
        with patch('web_fetch.core_fetcher.WebFetcher') as mock_fetcher:
            mock_result = MagicMock()
            mock_result.error = "Authentication failed: Invalid credentials"
            mock_result.status_code = 401
            mock_result.is_success = False

            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_single = AsyncMock(return_value=mock_result)
            mock_fetcher.return_value.__aenter__ = AsyncMock(return_value=mock_fetcher_instance)
            mock_fetcher.return_value.__aexit__ = AsyncMock(return_value=None)

            request = ResourceRequest(
                uri=AnyUrl("https://api.example.com/data"),
                kind=ResourceKind.API_AUTH
            )

            result = await component.fetch(request)
            assert not result.is_success
            assert "Authentication failed" in result.error

    @pytest.mark.asyncio
    async def test_database_connection_failure(self) -> None:
        """Test database component with connection failure."""
        db_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="invalid-host",
            port=5432,
            database="test",
            username="user",
            password=SecretStr("password")
        )
        component = DatabaseComponent(db_config=db_config)

        with patch('web_fetch.components.database_component.asyncpg') as mock_asyncpg:
            mock_asyncpg.create_pool.side_effect = Exception("Connection failed")

            request = ResourceRequest(
                uri=AnyUrl("postgresql://invalid-host:5432/test"),
                kind=ResourceKind.DATABASE,
                options={"query": {"query": "SELECT 1"}}
            )

            result = await component.fetch(request)
            assert result.error is not None
            assert "Database query error" in result.error

    @pytest.mark.asyncio
    async def test_cloud_storage_invalid_credentials(self) -> None:
        """Test cloud storage component with invalid credentials."""
        storage_config = CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key=SecretStr("invalid-key"),
            secret_key=SecretStr("invalid-secret")
        )
        component = CloudStorageComponent(storage_config=storage_config)

        with patch('web_fetch.components.cloud_storage_component.boto3') as mock_boto3:
            from botocore.exceptions import NoCredentialsError
            mock_client = MagicMock()
            mock_client.list_objects_v2.side_effect = NoCredentialsError()
            mock_session = MagicMock()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session

            request = ResourceRequest(
                uri=AnyUrl("s3://test-bucket"),
                kind=ResourceKind.CLOUD_STORAGE,
                options={
                    "operation": {
                        "operation": "list",
                        "prefix": ""
                    }
                }
            )

            result = await component.fetch(request)
            assert result.error is not None
            assert "Cloud storage error" in result.error


class TestExtendedComponentsIntegration:
    """Integration tests for extended components."""

    @pytest.mark.asyncio
    async def test_component_registry_integration(self) -> None:
        """Test that all new components are properly registered."""
        from web_fetch.components.base import component_registry

        # Check that all new resource kinds are registered
        available_components = component_registry.available()

        assert ResourceKind.RSS in available_components
        assert ResourceKind.API_AUTH in available_components
        assert ResourceKind.DATABASE in available_components
        assert ResourceKind.CLOUD_STORAGE in available_components

    @pytest.mark.asyncio
    async def test_resource_manager_integration(self) -> None:
        """Test integration with ResourceManager."""
        from web_fetch.components.manager import ResourceManager

        manager = ResourceManager()

        # Test that manager can create all new component types
        rss_component = manager.get_component(ResourceKind.RSS)
        assert isinstance(rss_component, RSSComponent)

        api_component = manager.get_component(ResourceKind.API_AUTH)
        assert isinstance(api_component, AuthenticatedAPIComponent)

        db_component = manager.get_component(ResourceKind.DATABASE)
        assert isinstance(db_component, DatabaseComponent)

        storage_component = manager.get_component(ResourceKind.CLOUD_STORAGE)
        assert isinstance(storage_component, CloudStorageComponent)

    @pytest.mark.asyncio
    async def test_convenience_functions_integration(self) -> None:
        """Test integration with convenience functions."""
        from web_fetch.convenience import (
            fetch_rss_feed, fetch_authenticated_api,
            execute_database_query, cloud_storage_operation
        )

        # These should not raise import errors
        assert callable(fetch_rss_feed)
        assert callable(fetch_authenticated_api)
        assert callable(execute_database_query)
        assert callable(cloud_storage_operation)
