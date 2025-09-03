# Enhanced Authentication System

The web-fetch library provides a comprehensive, production-ready authentication system with advanced features including secure credential management, retry policies, session management, and flexible configuration options.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Credential Management](#credential-management)
5. [Session Management](#session-management)
6. [Error Handling & Retry Policies](#error-handling--retry-policies)
7. [Security Features](#security-features)
8. [Production Deployment](#production-deployment)
9. [API Reference](#api-reference)

## Overview

The enhanced authentication system provides:

- **Multiple Authentication Methods**: API keys, OAuth 2.0, JWT, Basic Auth, Bearer tokens, and custom methods
- **Secure Credential Storage**: Encrypted storage with multiple backends (file, memory, keyring, vault)
- **Advanced Session Management**: Persistent sessions with automatic cleanup and limits
- **Retry Policies**: Configurable retry logic with circuit breaker patterns
- **Flexible Configuration**: Environment variables, configuration files, and programmatic setup
- **Production Features**: Comprehensive logging, health monitoring, and security controls

## Quick Start

### Basic Usage

```python
import asyncio
from web_fetch.auth import EnhancedAuthManager, AuthenticationConfig, EnhancedAPIKeyConfig, CredentialConfig, CredentialSource

# Create configuration
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

# Initialize manager
async def main():
    manager = EnhancedAuthManager(config=config)
    
    # Authenticate
    result = await manager.authenticate("api_key")
    if result.success:
        print(f"Authentication successful: {result.headers}")
    
    await manager.shutdown()

asyncio.run(main())
```

### Configuration File Usage

Create a configuration file `auth_config.json`:

```json
{
  "default_method": "oauth",
  "methods": {
    "oauth": {
      "auth_type": "oauth2",
      "name": "github_oauth",
      "authorization_url": "https://github.com/login/oauth/authorize",
      "token_url": "https://github.com/login/oauth/access_token",
      "client_id": {
        "source": "environment",
        "env_var": "GITHUB_CLIENT_ID"
      },
      "client_secret": {
        "source": "environment",
        "env_var": "GITHUB_CLIENT_SECRET"
      },
      "scopes": ["user", "repo"]
    }
  },
  "url_patterns": {
    "api.github.com": "oauth"
  }
}
```

Load and use the configuration:

```python
from pathlib import Path
from web_fetch.auth import EnhancedAuthManager

# Load from configuration file
manager = EnhancedAuthManager.from_config_file(Path("auth_config.json"))

# Authenticate for GitHub API
result = await manager.authenticate(url="https://api.github.com/user")
```

## Configuration

### Credential Sources

The system supports multiple credential sources:

```python
from web_fetch.auth import CredentialConfig, CredentialSource

# Direct credential (not recommended for production)
direct_cred = CredentialConfig(
    source=CredentialSource.DIRECT,
    value="my-secret-key"
)

# Environment variable (recommended)
env_cred = CredentialConfig(
    source=CredentialSource.ENVIRONMENT,
    env_var="API_KEY"
)

# File-based credential
file_cred = CredentialConfig(
    source=CredentialSource.FILE,
    file_path=Path("/secure/path/api_key.txt")
)

# System keyring (requires keyring package)
keyring_cred = CredentialConfig(
    source=CredentialSource.KEYRING,
    keyring_service="my_app",
    keyring_username="api_user"
)
```

### Retry Policies

Configure retry behavior for authentication failures:

```python
from web_fetch.auth import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    retry_on_status_codes=[401, 403, 429, 500, 502, 503, 504]
)
```

### Session Configuration

Configure session management:

```python
from web_fetch.auth import SessionConfig
from pathlib import Path

session_config = SessionConfig(
    enable_persistence=True,
    session_timeout=3600.0,  # 1 hour
    max_sessions=10,
    cleanup_interval=300.0,  # 5 minutes
    storage_path=Path("/app/sessions")
)
```

### Security Configuration

Configure security settings:

```python
from web_fetch.auth import SecurityConfig

security_config = SecurityConfig(
    encrypt_credentials=True,
    credential_rotation_interval=86400.0,  # 24 hours
    require_https=True,
    validate_certificates=True,
    mask_credentials_in_logs=True
)
```

## Credential Management

### Secure Storage

The system provides encrypted credential storage:

```python
from web_fetch.auth import EncryptedFileStore, CredentialManager
from pathlib import Path
import os

# Set master key for encryption
os.environ["WEBFETCH_MASTER_KEY"] = "your-secure-master-key"

# Create encrypted storage
store = EncryptedFileStore(Path("/secure/credentials"))
manager = CredentialManager(store)

# Store credential securely
await manager.store_resolved_credential(
    "api_key",
    CredentialConfig(source=CredentialSource.DIRECT, value="secret-key")
)

# Retrieve credential
credential = await manager.get_credential("api_key")
```

### Credential Rotation

Implement automatic credential rotation:

```python
# Configure rotation in auth config
config = EnhancedAPIKeyConfig(
    name="rotating_key",
    api_key=primary_key_config,
    fallback_keys=[backup_key_config],
    security_config=SecurityConfig(
        credential_rotation_interval=86400.0  # Rotate daily
    )
)
```

## Session Management

### Session Persistence

Sessions are automatically managed and persisted:

```python
# Get session information
sessions = await manager.get_session_info("oauth")
for session in sessions:
    print(f"Session {session.session_id}: {session.auth_method}")
    print(f"Created: {session.created_at}")
    print(f"Expires: {session.expires_at}")

# Manually refresh session
await manager.session_managers["oauth"].refresh_session(session.session_id)

# Clean up expired sessions
cleaned_count = await manager.cleanup_sessions()
print(f"Cleaned up {cleaned_count} expired sessions")
```

## Error Handling & Retry Policies

### Circuit Breaker Pattern

The system includes circuit breaker protection:

```python
# Get health status
status = await manager.get_health_status()
print(f"Overall healthy: {status['overall_healthy']}")

for method_name, method_status in status["methods"].items():
    print(f"{method_name}: {method_status['circuit_breaker_state']}")
    if not method_status["healthy"]:
        print(f"  Failure count: {method_status['failure_count']}")
```

### Custom Error Handling

Handle authentication errors gracefully:

```python
from web_fetch.auth import AuthenticationError, AuthErrorType

try:
    result = await manager.authenticate("api_key")
except AuthenticationError as e:
    if e.error_type == AuthErrorType.INVALID_CREDENTIALS:
        print("Invalid credentials - check your API key")
    elif e.error_type == AuthErrorType.RATE_LIMITED:
        print(f"Rate limited - retry after {e.retry_after} seconds")
    elif e.error_type == AuthErrorType.NETWORK_ERROR:
        print("Network error - will retry automatically")
    else:
        print(f"Authentication failed: {e}")
```

## Security Features

### Credential Encryption

All stored credentials are encrypted using industry-standard encryption:

- **Algorithm**: AES-256 with Fernet (symmetric encryption)
- **Key Derivation**: PBKDF2 with SHA-256
- **Salt**: Unique salt per installation
- **Iterations**: 100,000 iterations for key derivation

### Secure Logging

Credentials are automatically masked in logs:

```python
import logging

# Configure logging with security filter
from web_fetch.logging import setup_logging, SensitiveDataFilter

logger = logging.getLogger("web_fetch.auth")
logger.addFilter(SensitiveDataFilter())

# Credentials will be masked as [REDACTED] in logs
logger.info(f"Using API key: {api_key}")  # Logs: "Using API key: [REDACTED]"
```

### HTTPS Enforcement

Configure HTTPS requirements:

```python
security_config = SecurityConfig(
    require_https=True,
    validate_certificates=True
)

# This will reject non-HTTPS authentication attempts
config = EnhancedAPIKeyConfig(
    name="secure_api",
    api_key=credential_config,
    security_config=security_config
)
```

## Production Deployment

### Environment Variables

Set up environment variables for production:

```bash
# Master key for credential encryption
export WEBFETCH_MASTER_KEY="your-secure-master-key-here"

# API credentials
export GITHUB_CLIENT_ID="your-github-client-id"
export GITHUB_CLIENT_SECRET="your-github-client-secret"
export API_KEY="your-api-key"

# Configuration
export WEBFETCH_AUTH_DEFAULT_METHOD="oauth"
export WEBFETCH_AUTH_GLOBAL_TIMEOUT="30.0"
```

### Docker Configuration

Example Dockerfile configuration:

```dockerfile
FROM python:3.11-slim

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create secure directories
RUN mkdir -p /app/auth_storage/credentials /app/auth_storage/sessions
RUN chmod 700 /app/auth_storage

# Copy application
COPY . /app
WORKDIR /app

# Set secure permissions
RUN chown -R app:app /app/auth_storage

# Run as non-root user
USER app

CMD ["python", "main.py"]
```

### Health Monitoring

Implement health checks:

```python
from fastapi import FastAPI
from web_fetch.auth import EnhancedAuthManager

app = FastAPI()
auth_manager = EnhancedAuthManager.from_environment()

@app.get("/health/auth")
async def auth_health():
    status = await auth_manager.get_health_status()
    return {
        "status": "healthy" if status["overall_healthy"] else "unhealthy",
        "details": status
    }
```

### Monitoring and Alerting

Set up monitoring for authentication failures:

```python
import logging
from web_fetch.auth import AuthErrorType

# Custom handler for authentication alerts
class AuthAlertHandler(logging.Handler):
    def emit(self, record):
        if hasattr(record, 'auth_error_type'):
            if record.auth_error_type == AuthErrorType.INVALID_CREDENTIALS:
                # Send alert for credential issues
                send_alert("Invalid credentials detected", record.getMessage())
            elif record.auth_error_type == AuthErrorType.RATE_LIMITED:
                # Monitor rate limiting
                track_metric("auth.rate_limited", 1)

# Add to logger
auth_logger = logging.getLogger("web_fetch.auth")
auth_logger.addHandler(AuthAlertHandler())
```

## API Reference

### EnhancedAuthManager

The main authentication manager class.

#### Methods

- `authenticate(method_name, url, force_refresh, **kwargs)`: Perform authentication
- `refresh_credentials(method_name)`: Refresh credentials for a method
- `get_session_info(method_name)`: Get session information
- `cleanup_sessions(method_name)`: Clean up expired sessions
- `get_health_status()`: Get health status of all methods
- `shutdown()`: Shutdown manager and cleanup resources

#### Class Methods

- `from_config_file(config_path, storage_path)`: Create from configuration file
- `from_environment(prefix, storage_path)`: Create from environment variables

### Configuration Classes

- `AuthenticationConfig`: Main configuration container
- `EnhancedAPIKeyConfig`: Enhanced API key configuration
- `EnhancedOAuth2Config`: Enhanced OAuth 2.0 configuration
- `EnhancedJWTConfig`: Enhanced JWT configuration
- `CredentialConfig`: Credential source configuration
- `RetryPolicy`: Retry behavior configuration
- `SessionConfig`: Session management configuration
- `SecurityConfig`: Security settings configuration

For complete API documentation, see the inline docstrings and type hints in the source code.
