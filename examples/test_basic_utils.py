#!/usr/bin/env python3
"""
Basic test script for utility modules without importing the full web_fetch package.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_url_validator() -> None:
    """Test URLValidator functionality."""
    print("Testing URLValidator...")
    
    # Import required models directly
    from web_fetch.models.http import URLAnalysis
    
    # Import URLValidator
    from web_fetch.utils.validation import URLValidator
    
    # Test valid URLs
    valid_urls = [
        "https://example.com",
        "http://localhost:8080",
        "https://sub.domain.com/path?query=value"
    ]
    
    for url in valid_urls:
        result = URLValidator.is_valid_url(url)
        print(f"  {url}: {result}")
        assert result, f"Expected {url} to be valid"
    
    # Test invalid URLs
    invalid_urls = [
        "not-a-url",
        "javascript:alert('xss')",
        "file:///etc/passwd",
        ""
    ]
    
    for url in invalid_urls:
        result = URLValidator.is_valid_url(url)
        print(f"  {url}: {result}")
        assert not result, f"Expected {url} to be invalid"
    
    # Test URL analysis
    analysis = URLValidator.analyze_url("https://example.com:8080/path?query=value#fragment")
    assert analysis.is_valid
    assert analysis.scheme == "https"
    assert analysis.domain == "example.com"
    assert analysis.port == 8080
    assert analysis.is_secure
    
    print("  URLValidator tests passed!")


def test_response_analyzer() -> None:
    """Test ResponseAnalyzer functionality."""
    print("Testing ResponseAnalyzer...")
    
    # Import required models directly
    from web_fetch.models.http import HeaderAnalysis
    
    # Import ResponseAnalyzer
    from web_fetch.utils.response import ResponseAnalyzer
    
    # Test header analysis
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": "1024",
        "Server": "nginx/1.18.0",
        "Cache-Control": "max-age=3600",
        "ETag": '"abc123"',
        "Strict-Transport-Security": "max-age=31536000"
    }
    
    analysis = ResponseAnalyzer.analyze_headers(headers)
    assert analysis.content_type == "application/json; charset=utf-8"
    assert analysis.content_length == 1024
    assert analysis.server == "nginx/1.18.0"
    assert analysis.is_cacheable
    assert analysis.has_security_headers
    
    # Test content type detection
    json_content = b'{"test": true}'
    content_type = ResponseAnalyzer.detect_content_type({}, json_content)
    assert content_type == "application/json"
    
    html_content = b'<!DOCTYPE html><html><head><title>Test</title></head></html>'
    content_type = ResponseAnalyzer.detect_content_type({}, html_content)
    assert content_type == "text/html"
    
    print("  ResponseAnalyzer tests passed!")


def test_cache() -> None:
    """Test SimpleCache functionality."""
    print("Testing SimpleCache...")
    
    # Import required models directly
    from web_fetch.models.http import CacheConfig
    
    # Import SimpleCache
    from web_fetch.utils.cache import SimpleCache
    
    # Create cache with small size for testing
    config = CacheConfig(max_size=3, ttl_seconds=60)
    cache = SimpleCache(config)
    
    # Test basic operations
    cache.put("url1", "content1", {"header": "value"}, 200)
    entry = cache.get("url1")
    
    assert entry is not None
    assert entry.get_data() == "content1"
    assert entry.headers == {"header": "value"}
    assert entry.status_code == 200
    assert not entry.is_expired
    
    # Test cache miss
    assert cache.get("nonexistent") is None
    
    # Test cache size
    assert cache.size() == 1
    
    print("  SimpleCache tests passed!")


def test_rate_limiter() -> None:
    """Test RateLimiter functionality."""
    print("Testing RateLimiter...")
    
    # Import required models directly
    from web_fetch.models.http import RateLimitConfig
    
    # Import RateLimiter
    from web_fetch.utils.rate_limit import RateLimiter
    
    # Create rate limiter
    config = RateLimitConfig(requests_per_second=10.0, burst_size=5)
    limiter = RateLimiter(config)
    
    # Test stats
    stats = limiter.get_stats()
    assert 'global_tokens' in stats
    assert 'global_requests' in stats
    assert stats['global_tokens'] == 5  # Initial burst size
    assert stats['global_requests'] == 0
    
    print("  RateLimiter tests passed!")


if __name__ == "__main__":
    print("Running basic utility tests...")
    
    try:
        test_url_validator()
        test_response_analyzer()
        test_cache()
        test_rate_limiter()
        
        print("\nAll basic utility tests passed! ✅")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
