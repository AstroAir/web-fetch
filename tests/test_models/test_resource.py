"""
Comprehensive tests for resource models in web_fetch.models.resource module.

Tests unified resource component models including types, requests, responses, and configurations.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from web_fetch.models.resource import (
    ResourceKind,
    ResourceConfig,
    ResourceRequest,
    ResourceResult,
)


class TestResourceKind:
    """Test ResourceKind enumeration."""
    
    def test_all_resource_kinds(self):
        """Test all resource kind values."""
        assert ResourceKind.HTTP == "http"
        assert ResourceKind.FTP == "ftp"
        assert ResourceKind.GRAPHQL == "graphql"
        assert ResourceKind.WEBSOCKET == "websocket"
        assert ResourceKind.CRAWLER == "crawler"
        assert ResourceKind.FILE == "file"
        assert ResourceKind.RSS == "rss"
        assert ResourceKind.API_AUTH == "api_auth"
        assert ResourceKind.DATABASE == "database"
        assert ResourceKind.CLOUD_STORAGE == "cloud_storage"
    
    def test_resource_kind_string_behavior(self):
        """Test that ResourceKind behaves as string."""
        kind = ResourceKind.HTTP
        assert str(kind) == "http"
        assert kind == "http"
        assert kind in ["http", "ftp", "websocket"]


class TestResourceConfig:
    """Test ResourceConfig model."""
    
    def test_default_config(self):
        """Test default resource configuration."""
        config = ResourceConfig()
        assert config.enable_cache is True
        assert config.cache_ttl_seconds == 300
        assert config.trace_id is None
    
    def test_custom_config(self):
        """Test custom resource configuration."""
        config = ResourceConfig(
            enable_cache=False,
            cache_ttl_seconds=600,
            trace_id="trace-123"
        )
        assert config.enable_cache is False
        assert config.cache_ttl_seconds == 600
        assert config.trace_id == "trace-123"
    
    def test_cache_ttl_validation(self):
        """Test cache TTL validation."""
        # Valid values
        ResourceConfig(cache_ttl_seconds=1)
        ResourceConfig(cache_ttl_seconds=3600)
        
        # Invalid values
        with pytest.raises(ValidationError):
            ResourceConfig(cache_ttl_seconds=0)
        
        with pytest.raises(ValidationError):
            ResourceConfig(cache_ttl_seconds=-1)
    
    def test_config_inheritance(self):
        """Test that ResourceConfig inherits from BaseConfig."""
        config = ResourceConfig()
        # Should have BaseConfig settings
        assert config.model_config.use_enum_values is True
        assert config.model_config.validate_assignment is True
        assert config.model_config.extra == "forbid"


class TestResourceRequest:
    """Test ResourceRequest model."""
    
    def test_basic_request(self):
        """Test basic resource request."""
        request = ResourceRequest(
            uri="https://example.com",
            kind=ResourceKind.HTTP
        )
        assert str(request.uri) == "https://example.com/"
        assert request.kind == ResourceKind.HTTP
        assert request.headers is None
        assert request.params is None
        assert request.options == {}
        assert request.timeout_seconds is None
        assert request.use_cache is None
    
    def test_http_request_with_options(self):
        """Test HTTP request with headers and options."""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        params = {"page": 1, "limit": 10}
        options = {"method": "POST", "data": {"key": "value"}}
        
        request = ResourceRequest(
            uri="https://api.example.com/data",
            kind=ResourceKind.HTTP,
            headers=headers,
            params=params,
            options=options,
            timeout_seconds=30.0,
            use_cache=False
        )
        
        assert request.headers == headers
        assert request.params == params
        assert request.options == options
        assert request.timeout_seconds == 30.0
        assert request.use_cache is False
    
    def test_ftp_request(self):
        """Test FTP resource request."""
        options = {"operation": "download", "local_path": "/tmp/file.txt"}
        
        request = ResourceRequest(
            uri="ftp://ftp.example.com/path/file.txt",
            kind=ResourceKind.FTP,
            options=options
        )
        
        assert "ftp.example.com" in str(request.uri)
        assert request.kind == ResourceKind.FTP
        assert request.options == options
    
    def test_websocket_request(self):
        """Test WebSocket resource request."""
        options = {"subprotocols": ["chat"], "ping_interval": 20}
        
        request = ResourceRequest(
            uri="wss://ws.example.com/chat",
            kind=ResourceKind.WEBSOCKET,
            options=options
        )
        
        assert "ws.example.com" in str(request.uri)
        assert request.kind == ResourceKind.WEBSOCKET
        assert request.options == options
    
    def test_graphql_request(self):
        """Test GraphQL resource request."""
        options = {
            "query": "query { users { id name } }",
            "variables": {"limit": 10}
        }
        
        request = ResourceRequest(
            uri="https://api.example.com/graphql",
            kind=ResourceKind.GRAPHQL,
            options=options
        )
        
        assert request.kind == ResourceKind.GRAPHQL
        assert request.options == options
    
    def test_database_request(self):
        """Test database resource request."""
        options = {
            "query": "SELECT * FROM users WHERE active = ?",
            "parameters": [True],
            "fetch_mode": "all"
        }
        
        request = ResourceRequest(
            uri="postgresql://localhost:5432/mydb",
            kind=ResourceKind.DATABASE,
            options=options
        )
        
        assert request.kind == ResourceKind.DATABASE
        assert request.options == options
    
    def test_cloud_storage_request(self):
        """Test cloud storage resource request."""
        options = {
            "operation": "get",
            "bucket": "my-bucket",
            "key": "path/to/file.txt"
        }
        
        request = ResourceRequest(
            uri="s3://my-bucket/path/to/file.txt",
            kind=ResourceKind.CLOUD_STORAGE,
            options=options
        )
        
        assert request.kind == ResourceKind.CLOUD_STORAGE
        assert request.options == options
    
    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        ResourceRequest(
            uri="https://example.com",
            kind=ResourceKind.HTTP,
            timeout_seconds=10.5
        )
        
        # Invalid timeout
        with pytest.raises(ValidationError):
            ResourceRequest(
                uri="https://example.com",
                kind=ResourceKind.HTTP,
                timeout_seconds=0.0
            )
        
        with pytest.raises(ValidationError):
            ResourceRequest(
                uri="https://example.com",
                kind=ResourceKind.HTTP,
                timeout_seconds=-5.0
            )
    
    def test_enum_values_used(self):
        """Test that enum values are used in serialization."""
        request = ResourceRequest(
            uri="https://example.com",
            kind=ResourceKind.HTTP
        )
        
        # Should use enum value, not enum object
        data = request.model_dump()
        assert data["kind"] == "http"
        assert isinstance(data["kind"], str)


class TestResourceResult:
    """Test ResourceResult dataclass."""
    
    def test_default_result(self):
        """Test default resource result."""
        result = ResourceResult(url="https://example.com")
        assert result.url == "https://example.com"
        assert isinstance(result.timestamp, datetime)
        assert result.response_time == 0.0
        assert result.error is None
        assert result.retry_count == 0
        assert result.status_code is None
        assert result.headers == {}
        assert result.content is None
        assert result.content_type is None
        assert result.metadata == {}
    
    def test_http_success_result(self):
        """Test successful HTTP result."""
        headers = {"Content-Type": "application/json", "Content-Length": "100"}
        content = {"message": "success", "data": [1, 2, 3]}
        metadata = {"parsed_at": "2024-01-01T00:00:00Z"}
        
        result = ResourceResult(
            url="https://api.example.com/data",
            status_code=200,
            headers=headers,
            content=content,
            content_type="application/json",
            response_time=1.5,
            metadata=metadata
        )
        
        assert result.status_code == 200
        assert result.headers == headers
        assert result.content == content
        assert result.content_type == "application/json"
        assert result.response_time == 1.5
        assert result.metadata == metadata
        assert result.is_success is True
    
    def test_http_error_result(self):
        """Test HTTP error result."""
        result = ResourceResult(
            url="https://api.example.com/notfound",
            status_code=404,
            headers={"Content-Type": "text/plain"},
            content="Not Found",
            error="Resource not found",
            response_time=0.5
        )
        
        assert result.status_code == 404
        assert result.error == "Resource not found"
        assert result.is_success is False
    
    def test_non_http_success_result(self):
        """Test successful non-HTTP result (no status code)."""
        content = {"rows": [{"id": 1, "name": "test"}]}
        metadata = {"query_time": 0.05, "rows_affected": 1}
        
        result = ResourceResult(
            url="postgresql://localhost/db",
            content=content,
            metadata=metadata,
            response_time=0.1
        )
        
        assert result.status_code is None
        assert result.content == content
        assert result.metadata == metadata
        assert result.is_success is True  # No error and no status code = success
    
    def test_non_http_error_result(self):
        """Test error non-HTTP result."""
        result = ResourceResult(
            url="postgresql://localhost/db",
            error="Connection failed",
            response_time=5.0
        )
        
        assert result.status_code is None
        assert result.error == "Connection failed"
        assert result.is_success is False  # Has error = failure
    
    def test_is_success_status_codes(self):
        """Test is_success property with various status codes."""
        # Success codes (2xx)
        for code in [200, 201, 202, 204, 206]:
            result = ResourceResult(url="https://example.com", status_code=code)
            assert result.is_success is True, f"Status {code} should be success"
        
        # Client error codes (4xx)
        for code in [400, 401, 403, 404, 429]:
            result = ResourceResult(url="https://example.com", status_code=code)
            assert result.is_success is False, f"Status {code} should be failure"
        
        # Server error codes (5xx)
        for code in [500, 502, 503, 504]:
            result = ResourceResult(url="https://example.com", status_code=code)
            assert result.is_success is False, f"Status {code} should be failure"
        
        # Redirect codes (3xx) - considered failure
        for code in [301, 302, 304, 307]:
            result = ResourceResult(url="https://example.com", status_code=code)
            assert result.is_success is False, f"Status {code} should be failure"
    
    def test_complex_content_types(self):
        """Test result with various content types."""
        # JSON content
        json_result = ResourceResult(
            url="https://api.example.com",
            content={"key": "value"},
            content_type="application/json"
        )
        assert isinstance(json_result.content, dict)
        
        # Binary content
        binary_result = ResourceResult(
            url="https://example.com/file.pdf",
            content=b"PDF content here",
            content_type="application/pdf"
        )
        assert isinstance(binary_result.content, bytes)
        
        # Text content
        text_result = ResourceResult(
            url="https://example.com/page.html",
            content="<html><body>Hello</body></html>",
            content_type="text/html"
        )
        assert isinstance(text_result.content, str)
    
    def test_metadata_flexibility(self):
        """Test metadata field flexibility."""
        metadata = {
            "parser_version": "1.0",
            "extracted_links": ["https://link1.com", "https://link2.com"],
            "processing_time": 0.25,
            "cache_hit": True,
            "nested": {
                "level1": {
                    "level2": "deep value"
                }
            }
        }
        
        result = ResourceResult(
            url="https://example.com",
            metadata=metadata
        )
        
        assert result.metadata == metadata
        assert result.metadata["parser_version"] == "1.0"
        assert len(result.metadata["extracted_links"]) == 2
        assert result.metadata["nested"]["level1"]["level2"] == "deep value"
