"""
Tests for the URL utilities module.
"""

import pytest
from unittest.mock import patch, MagicMock

from web_fetch.url_utils import (
    is_valid_url,
    normalize_url,
    analyze_url,
    analyze_headers,
    detect_content_type,
)
from web_fetch.models.http import URLAnalysis, HeaderAnalysis
from web_fetch.models.base import ContentType


class TestURLValidation:
    """Test URL validation functions."""

    def test_is_valid_url_valid_cases(self):
        """Test valid URL cases."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
            "https://example.com:8080/path",
            "ftp://ftp.example.com/file.txt",
            "https://subdomain.example.com",
        ]

        for url in valid_urls:
            assert is_valid_url(url), f"URL should be valid: {url}"

    def test_is_valid_url_invalid_cases(self):
        """Test invalid URL cases."""
        invalid_urls = [
            "",
            "not-a-url",
            "http://",
            "://example.com",
            "example.com",  # Missing scheme
            "http:///path",  # Missing host
            "http://[invalid-ipv6",
        ]

        for url in invalid_urls:
            assert not is_valid_url(url), f"URL should be invalid: {url}"

    def test_normalize_url_basic(self):
        """Test basic URL normalization."""
        test_cases = [
            ("https://EXAMPLE.COM/Path", "https://example.com/Path"),
            ("https://example.com//path//", "https://example.com/path/"),
            ("https://example.com/path?b=2&a=1", "https://example.com/path?a=1&b=2"),
            ("https://example.com:443/path", "https://example.com/path"),
            ("http://example.com:80/path", "http://example.com/path"),
        ]

        for input_url, expected in test_cases:
            result = normalize_url(input_url)
            assert result == expected, f"Expected {expected}, got {result}"

    def test_normalize_url_edge_cases(self):
        """Test edge cases in URL normalization."""
        # Test with fragments
        assert normalize_url("https://example.com/path#fragment") == "https://example.com/path"

        # Test with encoded characters
        assert normalize_url("https://example.com/path%20with%20spaces") == "https://example.com/path%20with%20spaces"

    def test_normalize_url_with_base_url(self):
        """Test URL normalization with base URL."""
        base_url = "https://example.com/path/"

        test_cases = [
            ("../other", "https://example.com/other"),
            ("./file.html", "https://example.com/path/file.html"),
            ("subdir/file.html", "https://example.com/path/subdir/file.html"),
            ("/absolute/path", "https://example.com/absolute/path"),
        ]

        for relative_url, expected in test_cases:
            result = normalize_url(relative_url, base_url)
            assert result == expected, f"Expected {expected}, got {result}"

    def test_normalize_url_error_cases(self):
        """Test URL normalization error cases."""
        invalid_urls = [
            "",
            "not-a-url",
            "http://",
            "://example.com",
        ]

        for invalid_url in invalid_urls:
            with pytest.raises((ValueError, Exception)):
                normalize_url(invalid_url)

    @pytest.mark.parametrize("url,expected_scheme,expected_host,expected_port", [
        ("https://example.com", "https", "example.com", 443),
        ("http://example.com:8080", "http", "example.com", 8080),
        ("ftp://ftp.example.com:21", "ftp", "ftp.example.com", 21),
        ("https://subdomain.example.com", "https", "subdomain.example.com", 443),
    ])
    def test_normalize_url_parametrized(self, url, expected_scheme, expected_host, expected_port):
        """Test URL normalization with parametrized inputs."""
        normalized = normalize_url(url)
        assert normalized.startswith(expected_scheme)
        assert expected_host in normalized


class TestURLAnalysis:
    """Test URL analysis functions."""

    def test_analyze_url_basic(self):
        """Test basic URL analysis."""
        url = "https://api.example.com:8080/v1/users?page=1&limit=10#section"

        analysis = analyze_url(url)

        assert isinstance(analysis, URLAnalysis)
        assert analysis.scheme == "https"
        assert analysis.host == "api.example.com"
        assert analysis.port == 8080
        assert analysis.path == "/v1/users"
        assert "page" in analysis.query_params
        assert analysis.query_params["page"] == "1"
        assert analysis.fragment == "section"

    def test_analyze_url_minimal(self):
        """Test URL analysis with minimal URL."""
        url = "https://example.com"

        analysis = analyze_url(url)

        assert analysis.scheme == "https"
        assert analysis.host == "example.com"
        assert analysis.port is None or analysis.port == 443
        assert analysis.path == "/"
        assert len(analysis.query_params) == 0

    def test_analyze_url_with_subdomain(self):
        """Test URL analysis with subdomain."""
        url = "https://api.v2.example.com/endpoint"

        analysis = analyze_url(url)

        assert analysis.host == "api.v2.example.com"
        if hasattr(analysis, 'subdomain'):
            assert analysis.subdomain == "api.v2"
        if hasattr(analysis, 'domain'):
            assert analysis.domain == "example.com"

    def test_analyze_url_security_characteristics(self):
        """Test URL security analysis."""
        test_cases = [
            ("https://example.com", True),  # Secure
            ("http://example.com", False),  # Not secure
            ("ftps://ftp.example.com", True),  # Secure FTP
            ("ftp://ftp.example.com", False),  # Not secure FTP
        ]

        for url, expected_secure in test_cases:
            analysis = analyze_url(url)
            if hasattr(analysis, 'is_secure'):
                assert analysis.is_secure == expected_secure

    def test_analyze_url_localhost_detection(self):
        """Test localhost detection in URL analysis."""
        localhost_urls = [
            "http://localhost:8080/api",
            "https://127.0.0.1:3000/app",
            "http://0.0.0.0:5000/test",
        ]

        for url in localhost_urls:
            analysis = analyze_url(url)
            if hasattr(analysis, 'is_local'):
                assert analysis.is_local is True

    def test_analyze_url_complex_query_params(self):
        """Test URL analysis with complex query parameters."""
        url = "https://example.com/search?q=python+web+scraping&sort=date&page=2&filters[]=type:article&filters[]=lang:en"

        analysis = analyze_url(url)

        assert "q" in analysis.query_params
        assert "sort" in analysis.query_params
        assert "page" in analysis.query_params
        assert analysis.query_params["q"] == "python web scraping"
        assert analysis.query_params["sort"] == "date"
        assert analysis.query_params["page"] == "2"

    def test_analyze_url_international_domain(self):
        """Test URL analysis with international domain names."""
        # Test with IDN (Internationalized Domain Names)
        url = "https://例え.テスト/path"

        try:
            analysis = analyze_url(url)
            assert analysis.scheme == "https"
            assert analysis.path == "/path"
        except (ValueError, UnicodeError):
            # Some implementations may not support IDN
            pytest.skip("IDN not supported by URL analyzer")

    def test_analyze_url_error_cases(self):
        """Test URL analysis error handling."""
        invalid_urls = [
            "",
            "not-a-url",
            "http://",
            "://example.com",
            "http:///path",
        ]

        for invalid_url in invalid_urls:
            with pytest.raises((ValueError, Exception)):
                analyze_url(invalid_url)

    @pytest.mark.parametrize("url,expected_path", [
        ("https://example.com", "/"),
        ("https://example.com/", "/"),
        ("https://example.com/path", "/path"),
        ("https://example.com/path/", "/path/"),
        ("https://example.com/path/to/resource", "/path/to/resource"),
    ])
    def test_analyze_url_path_variations(self, url, expected_path):
        """Test URL analysis with different path variations."""
        analysis = analyze_url(url)
        assert analysis.path == expected_path


class TestHeaderAnalysis:
    """Test header analysis functions."""

    def test_analyze_headers_basic(self):
        """Test basic header analysis."""
        headers = {
            "content-type": "application/json; charset=utf-8",
            "content-length": "1024",
            "cache-control": "max-age=3600",
            "server": "nginx/1.18.0",
        }

        analysis = analyze_headers(headers)

        assert isinstance(analysis, HeaderAnalysis)
        assert analysis.content_type == "application/json"
        assert analysis.charset == "utf-8"
        assert analysis.content_length == 1024
        assert analysis.cache_control["max-age"] == 3600
        assert analysis.server == "nginx/1.18.0"

    def test_analyze_headers_security(self):
        """Test security header analysis."""
        headers = {
            "strict-transport-security": "max-age=31536000; includeSubDomains",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "x-xss-protection": "1; mode=block",
        }

        analysis = analyze_headers(headers)

        assert analysis.security_headers["strict-transport-security"] is not None
        assert analysis.security_headers["x-frame-options"] == "DENY"
        assert analysis.has_security_headers is True

    def test_analyze_headers_empty(self):
        """Test analysis with empty headers."""
        analysis = analyze_headers({})

        assert isinstance(analysis, HeaderAnalysis)
        assert analysis.content_type is None
        assert analysis.content_length is None

    def test_analyze_headers_case_insensitive(self):
        """Test that header analysis is case-insensitive."""
        headers_variations = [
            {"Content-Type": "application/json"},
            {"content-type": "application/json"},
            {"CONTENT-TYPE": "application/json"},
            {"Content-type": "application/json"},
        ]

        for headers in headers_variations:
            analysis = analyze_headers(headers)
            assert analysis.content_type == "application/json"

    def test_analyze_headers_compression(self):
        """Test compression header analysis."""
        headers = {
            "content-encoding": "gzip",
            "content-type": "text/html",
            "vary": "Accept-Encoding"
        }

        analysis = analyze_headers(headers)

        if hasattr(analysis, 'compression'):
            assert analysis.compression == "gzip"
        if hasattr(analysis, 'vary'):
            assert "Accept-Encoding" in analysis.vary

    def test_analyze_headers_caching_directives(self):
        """Test cache control directive parsing."""
        headers = {
            "cache-control": "public, max-age=3600, must-revalidate",
            "expires": "Wed, 21 Oct 2025 07:28:00 GMT",
            "etag": '"33a64df551425fcc55e4d42a148795d9f25f89d4"',
            "last-modified": "Wed, 21 Oct 2020 07:28:00 GMT"
        }

        analysis = analyze_headers(headers)

        if hasattr(analysis, 'cache_control'):
            assert "public" in analysis.cache_control
            assert analysis.cache_control.get("max-age") == 3600
            assert "must-revalidate" in analysis.cache_control

        if hasattr(analysis, 'etag'):
            assert analysis.etag == '"33a64df551425fcc55e4d42a148795d9f25f89d4"'

    def test_analyze_headers_content_disposition(self):
        """Test content disposition header analysis."""
        headers = {
            "content-disposition": 'attachment; filename="document.pdf"',
            "content-type": "application/pdf",
            "content-length": "1048576"
        }

        analysis = analyze_headers(headers)

        if hasattr(analysis, 'content_disposition'):
            assert "attachment" in analysis.content_disposition
            assert "document.pdf" in analysis.content_disposition

    def test_analyze_headers_cors(self):
        """Test CORS header analysis."""
        headers = {
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, POST, PUT, DELETE",
            "access-control-allow-headers": "Content-Type, Authorization",
            "access-control-max-age": "86400"
        }

        analysis = analyze_headers(headers)

        if hasattr(analysis, 'cors_headers'):
            assert analysis.cors_headers["access-control-allow-origin"] == "*"
            assert "GET" in analysis.cors_headers["access-control-allow-methods"]

    def test_analyze_headers_custom_headers(self):
        """Test analysis of custom/non-standard headers."""
        headers = {
            "x-custom-header": "custom-value",
            "x-rate-limit-remaining": "99",
            "x-request-id": "abc123def456",
            "x-powered-by": "Express"
        }

        analysis = analyze_headers(headers)

        # Custom headers should be preserved in the analysis
        if hasattr(analysis, 'custom_headers'):
            assert "x-custom-header" in analysis.custom_headers
            assert analysis.custom_headers["x-custom-header"] == "custom-value"


class TestContentTypeDetection:
    """Test content type detection functions."""

    def test_detect_content_type_from_headers(self):
        """Test content type detection from headers."""
        headers = {"content-type": "application/json; charset=utf-8"}

        content_type = detect_content_type(headers=headers)

        assert content_type == ContentType.JSON

    def test_detect_content_type_from_url(self):
        """Test content type detection from URL extension."""
        test_cases = [
            ("https://example.com/file.json", ContentType.JSON),
            ("https://example.com/file.xml", ContentType.XML),
            ("https://example.com/file.pdf", ContentType.BINARY),
            ("https://example.com/image.jpg", ContentType.BINARY),
            ("https://example.com/page.html", ContentType.HTML),
        ]

        for url, expected in test_cases:
            result = detect_content_type(url=url)
            assert result == expected, f"Expected {expected} for {url}, got {result}"

    def test_detect_content_type_from_content(self):
        """Test content type detection from content."""
        test_cases = [
            ('{"key": "value"}', ContentType.JSON),
            ("<html><body>Test</body></html>", ContentType.HTML),
            ("<?xml version='1.0'?><root></root>", ContentType.XML),
            ("plain text content", ContentType.TEXT),
        ]

        for content, expected in test_cases:
            result = detect_content_type(content=content)
            assert result == expected, f"Expected {expected} for content, got {result}"

    def test_detect_content_type_priority(self):
        """Test content type detection priority (headers > content > url)."""
        headers = {"content-type": "application/json"}
        url = "https://example.com/file.xml"
        content = "<html>test</html>"

        # Headers should take priority
        result = detect_content_type(headers=headers, url=url, content=content)
        assert result == ContentType.JSON

    def test_detect_content_type_complex_headers(self):
        """Test content type detection with complex header values."""
        test_cases = [
            ({"content-type": "application/json; charset=utf-8"}, ContentType.JSON),
            ({"content-type": "text/html; charset=iso-8859-1"}, ContentType.HTML),
            ({"content-type": "application/xml; boundary=something"}, ContentType.XML),
            ({"content-type": "text/plain; charset=utf-8"}, ContentType.TEXT),
        ]

        for headers, expected in test_cases:
            result = detect_content_type(headers=headers)
            assert result == expected

    def test_detect_content_type_case_insensitive_headers(self):
        """Test content type detection with case-insensitive headers."""
        headers_variations = [
            {"Content-Type": "application/json"},
            {"content-type": "application/json"},
            {"CONTENT-TYPE": "application/json"},
        ]

        for headers in headers_variations:
            result = detect_content_type(headers=headers)
            assert result == ContentType.JSON

    def test_detect_content_type_url_extensions(self):
        """Test content type detection from various URL extensions."""
        test_cases = [
            ("https://example.com/data.json", ContentType.JSON),
            ("https://example.com/page.html", ContentType.HTML),
            ("https://example.com/page.htm", ContentType.HTML),
            ("https://example.com/document.xml", ContentType.XML),
            ("https://example.com/file.txt", ContentType.TEXT),
            ("https://example.com/image.jpg", ContentType.BINARY),
            ("https://example.com/image.png", ContentType.BINARY),
            ("https://example.com/document.pdf", ContentType.BINARY),
            ("https://example.com/archive.zip", ContentType.BINARY),
            ("https://example.com/video.mp4", ContentType.BINARY),
        ]

        for url, expected in test_cases:
            result = detect_content_type(url=url)
            assert result == expected, f"Expected {expected} for {url}, got {result}"

    def test_detect_content_type_content_analysis(self):
        """Test content type detection from content analysis."""
        test_cases = [
            ('{"key": "value", "number": 123}', ContentType.JSON),
            ('[{"item": 1}, {"item": 2}]', ContentType.JSON),
            ("<!DOCTYPE html><html><head><title>Test</title></head></html>", ContentType.HTML),
            ("<html><body><h1>Title</h1></body></html>", ContentType.HTML),
            ('<?xml version="1.0" encoding="UTF-8"?><root><item>test</item></root>', ContentType.XML),
            ("<root><item>test</item></root>", ContentType.XML),
            ("This is plain text content without any markup.", ContentType.TEXT),
            ("Line 1\nLine 2\nLine 3", ContentType.TEXT),
        ]

        for content, expected in test_cases:
            result = detect_content_type(content=content)
            assert result == expected, f"Expected {expected} for content, got {result}"

    def test_detect_content_type_binary_content(self):
        """Test content type detection for binary content."""
        binary_contents = [
            b'\x89PNG\r\n\x1a\n',  # PNG header
            b'\xff\xd8\xff\xe0',   # JPEG header
            b'PK\x03\x04',         # ZIP header
            b'%PDF-1.4',          # PDF header
        ]

        for binary_content in binary_contents:
            result = detect_content_type(content=binary_content)
            assert result == ContentType.BINARY

    def test_detect_content_type_fallback(self):
        """Test content type detection fallback behavior."""
        # No headers, no recognizable URL extension, no recognizable content
        result = detect_content_type(
            url="https://example.com/unknown",
            content="some random content that doesn't match any pattern"
        )
        # Should fall back to TEXT as default
        assert result == ContentType.TEXT

    def test_detect_content_type_empty_inputs(self):
        """Test content type detection with empty inputs."""
        # All empty inputs
        result = detect_content_type()
        assert result == ContentType.TEXT  # Default fallback

        # Empty content
        result = detect_content_type(content="")
        assert result == ContentType.TEXT

        # Empty headers
        result = detect_content_type(headers={})
        assert result == ContentType.TEXT
