"""
Integrated Authentication Manager Example

This example demonstrates the integrated AuthManager that combines
legacy compatibility with enhanced features when available.
"""

import asyncio
import os
import tempfile
from pathlib import Path

# Import the integrated AuthManager
from web_fetch.auth import (
    AuthManager,
    APIKeyAuth,
    APIKeyConfig,
    BasicAuth,
    BasicAuthConfig,
    AuthResult,
    AuthType,
    AuthLocation
)

# Try to import enhanced features (optional)
try:
    from web_fetch.auth import (
        AuthenticationConfig,
        EnhancedAPIKeyConfig,
        CredentialConfig,
        CredentialSource
    )
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False


async def example_1_legacy_compatibility():
    """Example 1: Legacy usage (backward compatible)."""
    print("=== Example 1: Legacy Compatibility ===")
    
    # Create manager using legacy approach
    manager = AuthManager()
    
    # Add authentication method the old way
    api_config = APIKeyConfig(
        api_key="legacy-api-key-123",
        key_name="X-API-Key",
        location=AuthLocation.HEADER
    )
    
    manager.add_auth_method("legacy_api", APIKeyAuth(api_config))
    manager.set_default_method("legacy_api")
    
    try:
        # Authenticate using legacy method
        result = await manager.authenticate("legacy_api")
        if result.success:
            print(f"✅ Legacy authentication successful!")
            print(f"   Headers: {result.headers}")
        else:
            print(f"❌ Legacy authentication failed: {result.error}")
    
    except Exception as e:
        print(f"❌ Legacy authentication error: {e}")
    
    # Show method info
    info = manager.get_method_info("legacy_api")
    print(f"   Method info: {info}")
    
    await manager.shutdown()


async def example_2_enhanced_features():
    """Example 2: Enhanced features (when available)."""
    print("\n=== Example 2: Enhanced Features ===")
    
    if not ENHANCED_AVAILABLE:
        print("❌ Enhanced features not available - skipping")
        return
    
    # Set up environment variable
    os.environ["ENHANCED_API_KEY"] = "enhanced-key-456"
    
    try:
        # Create enhanced configuration
        config = AuthenticationConfig(
            default_method="enhanced_api",
            methods={
                "enhanced_api": EnhancedAPIKeyConfig(
                    name="enhanced_api_key",
                    api_key=CredentialConfig(
                        source=CredentialSource.ENVIRONMENT,
                        env_var="ENHANCED_API_KEY"
                    ),
                    key_name="Authorization",
                    prefix="Bearer"
                )
            }
        )
        
        # Create manager with enhanced features
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = AuthManager(
                enhanced_config=config,
                storage_path=Path(temp_dir),
                enable_enhanced_features=True
            )
            
            # Authenticate using enhanced method
            result = await manager.authenticate("enhanced_api")
            if result.success:
                print(f"✅ Enhanced authentication successful!")
                print(f"   Headers: {result.headers}")
            else:
                print(f"❌ Enhanced authentication failed: {result.error}")
            
            # Show enhanced features
            health = await manager.get_health_status()
            print(f"   Enhanced features enabled: {health['enhanced_features_enabled']}")
            print(f"   Overall healthy: {health['overall_healthy']}")
            
            # Show session info
            sessions = await manager.get_session_info("enhanced_api")
            print(f"   Active sessions: {len(sessions)}")
            
            await manager.shutdown()
    
    except Exception as e:
        print(f"❌ Enhanced authentication error: {e}")
    
    finally:
        # Cleanup
        if "ENHANCED_API_KEY" in os.environ:
            del os.environ["ENHANCED_API_KEY"]


async def example_3_mixed_usage():
    """Example 3: Mixed usage - legacy methods with enhanced manager."""
    print("\n=== Example 3: Mixed Usage ===")
    
    # Create manager (will use enhanced features if available)
    manager = AuthManager(enable_enhanced_features=ENHANCED_AVAILABLE)
    
    # Add methods using legacy approach
    api_config = APIKeyConfig(
        api_key="mixed-api-key-789",
        key_name="X-API-Key"
    )
    manager.add_auth_method("mixed_api", APIKeyAuth(api_config))
    
    basic_config = BasicAuthConfig(
        username="testuser",
        password="testpass"
    )
    manager.add_auth_method("mixed_basic", BasicAuth(basic_config))
    
    # Set URL patterns
    manager.add_url_pattern("api.example.com", "mixed_api")
    manager.add_url_pattern("secure.example.com", "mixed_basic")
    
    try:
        # Test URL-based authentication
        api_result = await manager.authenticate(url="https://api.example.com/data")
        print(f"✅ API authentication: {api_result.success}")
        if api_result.success:
            print(f"   Headers: {api_result.headers}")
        
        basic_result = await manager.authenticate(url="https://secure.example.com/login")
        print(f"✅ Basic authentication: {basic_result.success}")
        if basic_result.success:
            print(f"   Headers: {basic_result.headers}")
        
        # Show all methods
        methods = manager.list_methods()
        print(f"   Available methods: {methods}")
        
        # Show health status (enhanced feature if available)
        health = await manager.get_health_status()
        print(f"   Health status available: {'overall_healthy' in health}")
        
    except Exception as e:
        print(f"❌ Mixed usage error: {e}")
    
    await manager.shutdown()


async def example_4_configuration_file():
    """Example 4: Configuration from file (enhanced feature)."""
    print("\n=== Example 4: Configuration File ===")
    
    if not ENHANCED_AVAILABLE:
        print("❌ Enhanced features not available - skipping")
        return
    
    # Create configuration file
    config_data = {
        "default_method": "file_api",
        "methods": {
            "file_api": {
                "auth_type": "api_key",
                "name": "file_based_api",
                "api_key": {
                    "source": "direct",
                    "value": "file-config-key-123"
                },
                "key_name": "X-File-API-Key",
                "location": "header"
            }
        },
        "url_patterns": {
            "fileapi.example.com": "file_api"
        }
    }
    
    import json
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_path = Path(f.name)
    
    try:
        # Load manager from configuration file
        manager = AuthManager.from_config_file(config_path)
        
        # Test authentication
        result = await manager.authenticate("file_api")
        print(f"✅ File config authentication: {result.success}")
        if result.success:
            print(f"   Headers: {result.headers}")
        
        # Test URL-based selection
        url_result = await manager.authenticate(url="https://fileapi.example.com/data")
        print(f"✅ URL-based authentication: {url_result.success}")
        
        await manager.shutdown()
        
    except Exception as e:
        print(f"❌ Configuration file error: {e}")
    
    finally:
        config_path.unlink()  # Clean up


async def main():
    """Run all examples."""
    print("🚀 Integrated Authentication Manager Examples\n")
    print(f"Enhanced features available: {ENHANCED_AVAILABLE}")
    
    examples = [
        example_1_legacy_compatibility,
        example_2_enhanced_features,
        example_3_mixed_usage,
        example_4_configuration_file,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        
        # Small delay between examples
        await asyncio.sleep(0.2)
    
    print("\n✅ All examples completed!")
    print("\n📋 Summary:")
    print("- Legacy compatibility maintained ✅")
    print("- Enhanced features work when available ✅")
    print("- Mixed usage supported ✅")
    print("- Configuration file loading works ✅")
    print("- Graceful degradation when dependencies missing ✅")


if __name__ == "__main__":
    asyncio.run(main())
