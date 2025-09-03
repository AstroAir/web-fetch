"""
Enhanced Authentication Examples

This module demonstrates practical usage of the enhanced authentication system
with real-world scenarios and best practices.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any

from web_fetch.auth import (
    EnhancedAuthManager,
    AuthenticationConfig,
    EnhancedAPIKeyConfig,
    EnhancedOAuth2Config,
    EnhancedJWTConfig,
    CredentialConfig,
    CredentialSource,
    RetryPolicy,
    SessionConfig,
    SecurityConfig,
    AuthErrorType,
    AuthenticationError,
)


async def example_1_basic_api_key_auth():
    """Example 1: Basic API key authentication with environment variables."""
    print("=== Example 1: Basic API Key Authentication ===")
    
    # Set up environment variable (in production, this would be set externally)
    os.environ["MY_API_KEY"] = "sk-1234567890abcdef"
    
    # Create configuration
    config = AuthenticationConfig(
        default_method="api_key",
        methods={
            "api_key": EnhancedAPIKeyConfig(
                name="github_api",
                api_key=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="MY_API_KEY"
                ),
                key_name="Authorization",
                prefix="Bearer"
            )
        }
    )
    
    # Initialize manager
    manager = EnhancedAuthManager(config=config)
    
    try:
        # Authenticate
        result = await manager.authenticate("api_key")
        if result.success:
            print(f"✅ Authentication successful!")
            print(f"   Headers: {result.headers}")
        else:
            print(f"❌ Authentication failed: {result.error}")
    
    except AuthenticationError as e:
        print(f"❌ Authentication error: {e}")
    
    finally:
        await manager.shutdown()
        # Cleanup
        del os.environ["MY_API_KEY"]


async def example_2_oauth2_with_retry():
    """Example 2: OAuth 2.0 authentication with retry policies."""
    print("\n=== Example 2: OAuth 2.0 with Retry Policies ===")
    
    # Set up environment variables
    os.environ["OAUTH_CLIENT_ID"] = "your-client-id"
    os.environ["OAUTH_CLIENT_SECRET"] = "your-client-secret"
    
    # Create configuration with custom retry policy
    config = AuthenticationConfig(
        default_method="oauth",
        methods={
            "oauth": EnhancedOAuth2Config(
                name="github_oauth",
                authorization_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                client_id=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="OAUTH_CLIENT_ID"
                ),
                client_secret=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="OAUTH_CLIENT_SECRET"
                ),
                scopes=["user", "repo"],
                retry_policy=RetryPolicy(
                    max_attempts=5,
                    initial_delay=2.0,
                    max_delay=30.0,
                    exponential_base=2.0,
                    jitter=True
                )
            )
        },
        url_patterns={
            "api.github.com": "oauth"
        }
    )
    
    manager = EnhancedAuthManager(config=config)
    
    try:
        # Authenticate using URL pattern matching
        result = await manager.authenticate(url="https://api.github.com/user")
        print(f"✅ OAuth authentication configured (would require user interaction in real scenario)")
        
        # Show retry policy configuration
        oauth_config = config.methods["oauth"]
        print(f"   Retry policy: {oauth_config.retry_policy.max_attempts} attempts")
        print(f"   Initial delay: {oauth_config.retry_policy.initial_delay}s")
        
    except AuthenticationError as e:
        print(f"❌ OAuth error: {e}")
    
    finally:
        await manager.shutdown()
        # Cleanup
        del os.environ["OAUTH_CLIENT_ID"]
        del os.environ["OAUTH_CLIENT_SECRET"]


async def example_3_jwt_with_sessions():
    """Example 3: JWT authentication with session management."""
    print("\n=== Example 3: JWT with Session Management ===")
    
    # Set up JWT secret
    os.environ["JWT_SECRET"] = "your-jwt-secret-key"
    
    # Create configuration with session management
    config = AuthenticationConfig(
        default_method="jwt",
        methods={
            "jwt": EnhancedJWTConfig(
                name="api_jwt",
                secret_key=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="JWT_SECRET"
                ),
                algorithm="HS256",
                issuer="my-app",
                audience="api-users",
                expires_in=3600.0,  # 1 hour
                session_config=SessionConfig(
                    enable_persistence=True,
                    session_timeout=7200.0,  # 2 hours
                    max_sessions=5,
                    cleanup_interval=300.0  # 5 minutes
                )
            )
        }
    )
    
    # Use temporary directory for session storage
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = EnhancedAuthManager(config=config, storage_path=Path(temp_dir))
        
        try:
            # Authenticate and create session
            result = await manager.authenticate("jwt")
            print(f"✅ JWT authentication successful!")
            
            # Check session information
            sessions = await manager.get_session_info("jwt")
            print(f"   Active sessions: {len(sessions)}")
            
            if sessions:
                session = sessions[0]
                print(f"   Session ID: {session.session_id}")
                print(f"   Created: {session.created_at}")
                print(f"   Expires: {session.expires_at}")
            
            # Demonstrate session reuse
            result2 = await manager.authenticate("jwt")
            print(f"✅ Second authentication (should reuse session)")
            
        except AuthenticationError as e:
            print(f"❌ JWT error: {e}")
        
        finally:
            await manager.shutdown()
            del os.environ["JWT_SECRET"]


async def example_4_multiple_providers_with_failover():
    """Example 4: Multiple authentication providers with failover."""
    print("\n=== Example 4: Multiple Providers with Failover ===")
    
    # Set up multiple API keys
    os.environ["PRIMARY_API_KEY"] = "primary-key-123"
    os.environ["BACKUP_API_KEY"] = "backup-key-456"
    
    # Create configuration with multiple providers
    config = AuthenticationConfig(
        default_method="multi_api",
        methods={
            "multi_api": EnhancedAPIKeyConfig(
                name="multi_provider_api",
                api_key=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="PRIMARY_API_KEY"
                ),
                fallback_keys=[
                    CredentialConfig(
                        source=CredentialSource.ENVIRONMENT,
                        env_var="BACKUP_API_KEY"
                    )
                ],
                key_name="X-API-Key",
                retry_policy=RetryPolicy(
                    max_attempts=3,
                    initial_delay=1.0,
                    retry_on_status_codes=[401, 403, 429, 500, 502, 503]
                )
            )
        }
    )
    
    manager = EnhancedAuthManager(config=config)
    
    try:
        # Authenticate with primary provider
        result = await manager.authenticate("multi_api")
        print(f"✅ Multi-provider authentication successful!")
        print(f"   Using key: {result.headers.get('X-API-Key', 'N/A')}")
        
        # Show health status
        health = await manager.get_health_status()
        print(f"   System health: {'✅ Healthy' if health['overall_healthy'] else '❌ Unhealthy'}")
        
    except AuthenticationError as e:
        print(f"❌ Multi-provider error: {e}")
    
    finally:
        await manager.shutdown()
        # Cleanup
        del os.environ["PRIMARY_API_KEY"]
        del os.environ["BACKUP_API_KEY"]


async def example_5_configuration_file():
    """Example 5: Loading configuration from file."""
    print("\n=== Example 5: Configuration from File ===")
    
    # Create a comprehensive configuration
    config_data = {
        "default_method": "github_api",
        "global_timeout": 30.0,
        "global_retry_policy": {
            "max_attempts": 3,
            "initial_delay": 1.0,
            "max_delay": 60.0,
            "exponential_base": 2.0,
            "jitter": True
        },
        "global_security_config": {
            "encrypt_credentials": True,
            "require_https": True,
            "validate_certificates": True,
            "mask_credentials_in_logs": True
        },
        "methods": {
            "github_api": {
                "auth_type": "api_key",
                "name": "github_personal_token",
                "description": "GitHub Personal Access Token",
                "api_key": {
                    "source": "environment",
                    "env_var": "GITHUB_TOKEN"
                },
                "key_name": "Authorization",
                "prefix": "token",
                "location": "header",
                "retry_policy": {
                    "max_attempts": 5,
                    "initial_delay": 2.0
                },
                "session_config": {
                    "enable_persistence": True,
                    "session_timeout": 3600.0,
                    "max_sessions": 3
                }
            },
            "slack_webhook": {
                "auth_type": "bearer",
                "name": "slack_bot_token",
                "token": {
                    "source": "environment",
                    "env_var": "SLACK_BOT_TOKEN"
                },
                "token_prefix": "Bearer"
            }
        },
        "url_patterns": {
            "api.github.com": "github_api",
            "hooks.slack.com": "slack_webhook"
        },
        "environment": "production"
    }
    
    # Set up environment variables
    os.environ["GITHUB_TOKEN"] = "ghp_1234567890abcdef"
    os.environ["SLACK_BOT_TOKEN"] = "xoxb-1234567890"
    
    # Save configuration to temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f, indent=2)
        config_path = Path(f.name)
    
    try:
        # Load manager from configuration file
        manager = EnhancedAuthManager.from_config_file(config_path)
        
        # Test GitHub API authentication
        github_result = await manager.authenticate(url="https://api.github.com/user")
        print(f"✅ GitHub API auth: {github_result.success}")
        
        # Test Slack webhook authentication
        slack_result = await manager.authenticate(url="https://hooks.slack.com/services/...")
        print(f"✅ Slack webhook auth: {slack_result.success}")
        
        # Show configuration summary
        print(f"   Loaded {len(manager.config.methods)} authentication methods")
        print(f"   URL patterns: {len(manager.config.url_patterns)}")
        print(f"   Environment: {manager.config.environment}")
        
    except Exception as e:
        print(f"❌ Configuration file error: {e}")
    
    finally:
        await manager.shutdown()
        config_path.unlink()  # Clean up temp file
        # Cleanup environment
        del os.environ["GITHUB_TOKEN"]
        del os.environ["SLACK_BOT_TOKEN"]


async def example_6_error_handling_and_monitoring():
    """Example 6: Comprehensive error handling and monitoring."""
    print("\n=== Example 6: Error Handling and Monitoring ===")
    
    # Create configuration that will demonstrate various error scenarios
    config = AuthenticationConfig(
        default_method="test_api",
        methods={
            "test_api": EnhancedAPIKeyConfig(
                name="test_api_key",
                api_key=CredentialConfig(
                    source=CredentialSource.ENVIRONMENT,
                    env_var="NONEXISTENT_KEY"  # This will cause an error
                ),
                key_name="X-API-Key",
                retry_policy=RetryPolicy(
                    max_attempts=2,
                    initial_delay=0.1,
                    max_delay=1.0
                )
            )
        }
    )
    
    manager = EnhancedAuthManager(config=config)
    
    try:
        # This will fail due to missing environment variable
        result = await manager.authenticate("test_api")
        print(f"Unexpected success: {result}")
        
    except AuthenticationError as e:
        print(f"✅ Caught expected authentication error:")
        print(f"   Error type: {e.error_type}")
        print(f"   Message: {e}")
        print(f"   Is retryable: {e.is_retryable}")
        print(f"   Status code: {e.status_code}")
        
        # Demonstrate error classification
        if e.error_type == AuthErrorType.CONFIGURATION_ERROR:
            print("   → This is a configuration error - check your settings")
        elif e.error_type == AuthErrorType.INVALID_CREDENTIALS:
            print("   → Invalid credentials - check your API key")
        elif e.error_type == AuthErrorType.NETWORK_ERROR:
            print("   → Network error - check connectivity")
    
    # Show health status after error
    health = await manager.get_health_status()
    print(f"\n   Health status after error:")
    print(f"   Overall healthy: {health['overall_healthy']}")
    
    for method_name, method_status in health["methods"].items():
        print(f"   {method_name}:")
        print(f"     Circuit breaker: {method_status['circuit_breaker_state']}")
        print(f"     Failure count: {method_status['failure_count']}")
        print(f"     Healthy: {method_status['healthy']}")
    
    await manager.shutdown()


async def main():
    """Run all examples."""
    print("🚀 Enhanced Authentication System Examples\n")
    
    examples = [
        example_1_basic_api_key_auth,
        example_2_oauth2_with_retry,
        example_3_jwt_with_sessions,
        example_4_multiple_providers_with_failover,
        example_5_configuration_file,
        example_6_error_handling_and_monitoring,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        
        # Small delay between examples
        await asyncio.sleep(0.5)
    
    print("\n✅ All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
