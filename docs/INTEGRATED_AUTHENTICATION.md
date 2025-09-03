# Integrated Authentication System

The web-fetch library now provides a unified `AuthManager` that seamlessly combines legacy compatibility with enhanced features. This integration ensures backward compatibility while providing advanced capabilities when dependencies are available.

## Overview

The integrated `AuthManager` provides:

- **Full Backward Compatibility**: All existing code continues to work unchanged
- **Enhanced Features**: Advanced capabilities when optional dependencies are installed
- **Graceful Degradation**: Automatically falls back to basic functionality when enhanced features are unavailable
- **Unified API**: Single manager class for all authentication needs

## Key Features

### Legacy Compatibility ✅
- All existing `AuthManager` methods work unchanged
- No breaking changes to existing APIs
- Same configuration format support

### Enhanced Features (Optional) ✅
- Secure credential storage with encryption
- Retry policies and circuit breaker patterns
- Session management with persistence
- Multiple provider support with failover
- Comprehensive logging and debugging
- Environment-based configuration

### Graceful Degradation ✅
- Automatically detects available dependencies
- Falls back to basic functionality when enhanced features unavailable
- No errors when optional dependencies missing

## Usage Examples

### 1. Legacy Usage (Unchanged)

```python
from web_fetch.auth import AuthManager, APIKeyAuth, APIKeyConfig

# Create manager the old way
manager = AuthManager()

# Add authentication method
api_config = APIKeyConfig(
    api_key="your-api-key",
    key_name="X-API-Key"
)
manager.add_auth_method("api", APIKeyAuth(api_config))

# Authenticate
result = await manager.authenticate("api")
```

### 2. Enhanced Usage (When Available)

```python
from web_fetch.auth import AuthManager, AuthenticationConfig, EnhancedAPIKeyConfig, CredentialConfig, CredentialSource

# Create enhanced configuration
config = AuthenticationConfig(
    default_method="api_key",
    methods={
        "api_key": EnhancedAPIKeyConfig(
            name="my_api_key",
            api_key=CredentialConfig(
                source=CredentialSource.ENVIRONMENT,
                env_var="MY_API_KEY"
            ),
            key_name="X-API-Key"
        )
    }
)

# Create manager with enhanced features
manager = AuthManager(
    enhanced_config=config,
    storage_path=Path("/secure/storage"),
    enable_enhanced_features=True
)

# Authenticate with enhanced features (retry, sessions, etc.)
result = await manager.authenticate("api_key")
```

### 3. Mixed Usage

```python
from web_fetch.auth import AuthManager, APIKeyAuth, APIKeyConfig

# Create manager (will use enhanced features if available)
manager = AuthManager(enable_enhanced_features=True)

# Add methods using legacy approach
api_config = APIKeyConfig(api_key="legacy-key", key_name="X-API-Key")
manager.add_auth_method("legacy_api", APIKeyAuth(api_config))

# Use enhanced features if available
health = await manager.get_health_status()
sessions = await manager.get_session_info("legacy_api")
```

### 4. Configuration File Loading

```python
from web_fetch.auth import AuthManager
from pathlib import Path

# Load from configuration file (enhanced feature)
try:
    manager = AuthManager.from_config_file(Path("auth_config.json"))
except AttributeError:
    # Fallback for when enhanced features unavailable
    manager = AuthManager()
    # Add methods manually
```

## API Reference

### AuthManager

The unified authentication manager class.

#### Constructor

```python
AuthManager(
    enhanced_config: Optional[AuthenticationConfig] = None,
    credential_store: Optional[CredentialStore] = None,
    storage_path: Optional[Path] = None,
    enable_enhanced_features: bool = True
)
```

**Parameters:**
- `enhanced_config`: Enhanced authentication configuration (optional)
- `credential_store`: Custom credential store (optional)
- `storage_path`: Path for credential and session storage (optional)
- `enable_enhanced_features`: Whether to enable enhanced features if available

#### Legacy Methods (Always Available)

- `add_auth_method(name, auth_method)`: Add authentication method
- `remove_auth_method(name)`: Remove authentication method
- `set_default_method(name)`: Set default method
- `add_url_pattern(pattern, method_name)`: Add URL pattern
- `authenticate(method_name, **kwargs)`: Perform authentication
- `authenticate_for_url(url, **kwargs)`: Authenticate for URL
- `refresh(method_name)`: Refresh authentication
- `clear_cache(method_name)`: Clear cache
- `list_methods()`: List available methods
- `get_method_info(method_name)`: Get method information

#### Enhanced Methods (When Available)

- `authenticate(method_name, url, force_refresh, **kwargs)`: Enhanced authentication with retry
- `refresh_credentials(method_name)`: Refresh credentials
- `get_session_info(method_name)`: Get session information
- `cleanup_sessions(method_name)`: Clean up expired sessions
- `get_health_status()`: Get health status
- `shutdown()`: Shutdown and cleanup

#### Class Methods

- `create_from_config(config_dict)`: Create from configuration dictionary (legacy)
- `from_config_file(config_path, storage_path, enable_enhanced_features)`: Create from file (enhanced)
- `from_environment(prefix, storage_path, enable_enhanced_features)`: Create from environment (enhanced)

## Feature Detection

You can check which features are available:

```python
from web_fetch.auth import AuthManager

# Create manager
manager = AuthManager()

# Check if enhanced features are enabled
health = await manager.get_health_status()
enhanced_enabled = health.get("enhanced_features_enabled", False)

if enhanced_enabled:
    print("Enhanced features available")
    # Use enhanced features
    sessions = await manager.get_session_info("method_name")
else:
    print("Using basic features only")
    # Use legacy features only
```

## Migration Guide

### From Legacy AuthManager

No changes required! Your existing code will continue to work:

```python
# This code remains unchanged
manager = AuthManager()
manager.add_auth_method("api", APIKeyAuth(config))
result = await manager.authenticate("api")
```

### To Enhanced Features

Gradually adopt enhanced features:

```python
# Step 1: Enable enhanced features
manager = AuthManager(enable_enhanced_features=True)

# Step 2: Add legacy methods (still works)
manager.add_auth_method("api", APIKeyAuth(config))

# Step 3: Use enhanced features when available
if hasattr(manager, 'get_health_status'):
    health = await manager.get_health_status()
```

### Full Enhanced Migration

For new projects, use enhanced configuration:

```python
# Create enhanced configuration
config = AuthenticationConfig(...)

# Create enhanced manager
manager = AuthManager(enhanced_config=config)
```

## Dependencies

### Core Dependencies (Always Required)
- `pydantic` - For configuration models
- `aiohttp` - For HTTP operations

### Enhanced Dependencies (Optional)
- `cryptography` - For secure credential storage
- `keyring` - For system keyring integration (optional)
- `pyyaml` - For YAML configuration files (optional)

### Installation

```bash
# Basic installation
pip install pydantic aiohttp

# Enhanced features
pip install pydantic aiohttp cryptography

# Full features
pip install pydantic aiohttp cryptography keyring pyyaml
```

## Error Handling

The integrated manager handles missing dependencies gracefully:

```python
from web_fetch.auth import AuthManager

try:
    # Try to use enhanced features
    manager = AuthManager.from_config_file("config.json")
except (ImportError, AttributeError):
    # Fallback to basic features
    manager = AuthManager()
    # Configure manually
```

## Best Practices

1. **Start Simple**: Begin with legacy methods, add enhanced features gradually
2. **Feature Detection**: Check for enhanced features before using them
3. **Graceful Degradation**: Always provide fallbacks for missing features
4. **Configuration**: Use configuration files for complex setups
5. **Testing**: Test both enhanced and basic modes

## Troubleshooting

### Enhanced Features Not Available

If enhanced features aren't working:

1. Check dependencies: `pip install cryptography pydantic`
2. Verify imports: `from web_fetch.auth import AuthenticationConfig`
3. Enable explicitly: `AuthManager(enable_enhanced_features=True)`

### Legacy Code Not Working

If existing code breaks:

1. Ensure basic dependencies installed: `pip install pydantic`
2. Check for import errors in logs
3. Use basic manager: `AuthManager(enable_enhanced_features=False)`

The integrated authentication system provides the best of both worlds: full backward compatibility with powerful enhanced features when available.
