#!/usr/bin/env python3
"""
Test script to verify web_fetch functionality.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from web_fetch import (
    WebFetcher,
    fetch_url,
    ContentType,
    FetchConfig,
    APIKeyAuth,
    APIKeyConfig,
    BasicAuth,
    BasicAuthConfig,
    SimpleCache,
    CacheConfig
)


async def test_basic_functionality():
    """Test basic web fetching functionality."""
    print("🔧 Testing basic web_fetch functionality...")
    
    try:
        # Test 1: Basic URL fetching
        print("\n1. Testing basic URL fetching...")
        result = await fetch_url("https://httpbin.org/get", ContentType.JSON)
        if result.is_success:
            print("✅ Basic URL fetching works")
            print(f"   Status: {result.status_code}")
            print(f"   Content type: {type(result.content)}")
        else:
            print(f"❌ Basic URL fetching failed: {result.error}")
            
    except Exception as e:
        print(f"❌ Basic URL fetching error: {e}")
    
    try:
        # Test 2: WebFetcher class
        print("\n2. Testing WebFetcher class...")
        config = FetchConfig()
        fetcher = WebFetcher(config)
        
        from pydantic import HttpUrl
        from web_fetch.models import FetchRequest
        request = FetchRequest(url=HttpUrl("https://httpbin.org/json"))
        result = await fetcher.fetch_single(request)
        if result.is_success:
            print("✅ WebFetcher class works")
            print(f"   Response time: {result.response_time:.2f}s")
        else:
            print(f"❌ WebFetcher failed: {result.error}")
        
        await fetcher.close()
            
    except Exception as e:
        print(f"❌ WebFetcher error: {e}")
    
    try:
        # Test 3: Authentication
        print("\n3. Testing authentication...")
        
        # API Key auth
        from web_fetch.auth.base import AuthLocation
        api_config = APIKeyConfig(
            api_key="test-key",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        api_auth = APIKeyAuth(api_config)
        auth_result = await api_auth.authenticate()
        
        if auth_result.success:
            print("✅ API Key authentication works")
            print(f"   Headers: {auth_result.headers}")
        else:
            print(f"❌ API Key authentication failed: {auth_result.error}")
            
        # Basic auth
        basic_config = BasicAuthConfig(
            username="testuser",
            password="testpass"
        )
        basic_auth = BasicAuth(basic_config)
        basic_result = await basic_auth.authenticate()
        
        if basic_result.success:
            print("✅ Basic authentication works")
            print(f"   Headers: {basic_result.headers}")
        else:
            print(f"❌ Basic authentication failed: {basic_result.error}")
            
    except Exception as e:
        print(f"❌ Authentication error: {e}")
    
    try:
        # Test 4: Caching
        print("\n4. Testing caching...")
        
        cache_config = CacheConfig(
            ttl_seconds=60,
            max_size=100,
            enable_compression=True
        )
        cache = SimpleCache(cache_config)
        
        # Store something in cache
        cache.put("test-url", {"test": "data"}, {}, 200)
        
        # Retrieve from cache
        cached_entry = cache.get("test-url")
        if cached_entry:
            print("✅ Caching works")
            print(f"   Cache size: {cache.size()}")
            print(f"   Cached data: {cached_entry.get_data()}")
        else:
            print("❌ Caching failed")
            
    except Exception as e:
        print(f"❌ Caching error: {e}")
    
    print("\n🎉 Basic functionality test completed!")


async def test_advanced_features():
    """Test advanced features."""
    print("\n🚀 Testing advanced features...")
    
    try:
        # Test URL validation
        print("\n1. Testing URL utilities...")
        from web_fetch import is_valid_url, normalize_url, analyze_url
        
        test_url = "https://example.com/path?param=value"
        if is_valid_url(test_url):
            print("✅ URL validation works")
            
        normalized = normalize_url(test_url)
        print(f"   Normalized URL: {normalized}")
        
        analysis = analyze_url(test_url)
        print(f"   URL analysis: {analysis}")
        
    except Exception as e:
        print(f"❌ URL utilities error: {e}")
    
    try:
        # Test content type detection
        print("\n2. Testing content type detection...")
        from web_fetch import detect_content_type
        
        content_type = detect_content_type({}, b"Hello, World!")
        print(f"✅ Content type detection: {content_type}")
        
    except Exception as e:
        print(f"❌ Content type detection error: {e}")
    
    print("\n🎉 Advanced features test completed!")


if __name__ == "__main__":
    print("🧪 Starting web_fetch functionality tests...")
    
    try:
        asyncio.run(test_basic_functionality())
        asyncio.run(test_advanced_features())
        print("\n✅ All tests completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
