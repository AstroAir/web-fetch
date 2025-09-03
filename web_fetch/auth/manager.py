"""
Authentication manager for coordinating multiple authentication methods.

This module provides a centralized manager for handling different authentication
methods and applying them to requests. Enhanced with secure credential storage,
retry policies, session management, and comprehensive configuration support.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .api_key import APIKeyAuth, APIKeyConfig
from .base import AuthMethod, AuthResult, AuthType, AuthenticationError
from .basic import BasicAuth, BasicAuthConfig
from .bearer import BearerTokenAuth, BearerTokenConfig
from .custom import CustomAuth, CustomAuthConfig
from .jwt import JWTAuth, JWTConfig
from .oauth import OAuth2Auth, OAuth2Config

# Enhanced imports (optional dependencies)
try:
    from .config import AuthenticationConfig, EnhancedAuthConfig
    from .credential_store import CredentialManager, CredentialStore, EncryptedFileStore, InMemoryStore
    from .retry import RetryHandler, CircuitBreaker, classify_error
    from .session import SessionManager, SessionInfo
    ENHANCED_FEATURES_AVAILABLE = True
except ImportError:
    ENHANCED_FEATURES_AVAILABLE = False


logger = logging.getLogger(__name__)


class AuthManager:
    """
    Authentication manager for coordinating multiple authentication methods.

    The AuthManager provides a centralized way to manage and apply different
    authentication methods to HTTP requests. It supports multiple authentication
    methods and can automatically select the appropriate method based on URL
    patterns or other criteria.

    Enhanced features (when available):
    - Secure credential storage and management
    - Retry policies and circuit breaker patterns
    - Session management with persistence
    - Multiple provider support with failover
    - Comprehensive logging and debugging
    - Environment-based configuration

    Examples:
        Basic usage (legacy compatible):
        ```python
        # API key authentication
        api_config = APIKeyConfig(
            api_key="your-api-key",
            key_name="X-API-Key"
        )

        manager = AuthManager()
        manager.add_auth_method("api", APIKeyAuth(api_config))

        # Apply authentication to request
        auth_data = await manager.authenticate("api")
        ```

        Enhanced usage (with configuration):
        ```python
        # Load from configuration file
        manager = AuthManager.from_config_file("auth_config.json")

        # Or create with enhanced features
        manager = AuthManager(
            enhanced_config=auth_config,
            storage_path=Path("/secure/storage")
        )
        ```
    """

    def __init__(
        self,
        enhanced_config: Optional["AuthenticationConfig"] = None,
        credential_store: Optional["CredentialStore"] = None,
        storage_path: Optional[Path] = None,
        enable_enhanced_features: bool = True
    ) -> None:
        """
        Initialize the authentication manager.

        Args:
            enhanced_config: Enhanced authentication configuration (optional)
            credential_store: Custom credential store (optional)
            storage_path: Path for credential and session storage (optional)
            enable_enhanced_features: Whether to enable enhanced features if available
        """
        # Core authentication components
        self._auth_methods: Dict[str, AuthMethod] = {}
        self._default_method: Optional[str] = None
        self._url_patterns: Dict[str, str] = {}  # URL pattern -> auth method name

        # Enhanced features (if available and enabled)
        self._enhanced_features_enabled = enable_enhanced_features and ENHANCED_FEATURES_AVAILABLE

        if self._enhanced_features_enabled and enhanced_config:
            self._initialize_enhanced_features(enhanced_config, credential_store, storage_path)
        else:
            # Initialize minimal enhanced components for compatibility
            self.credential_manager = None
            self.session_managers: Dict[str, "SessionManager"] = {}
            self._retry_handlers: Dict[str, "RetryHandler"] = {}
            self._circuit_breakers: Dict[str, "CircuitBreaker"] = {}

    def _initialize_enhanced_features(
        self,
        config: "AuthenticationConfig",
        credential_store: Optional["CredentialStore"] = None,
        storage_path: Optional[Path] = None
    ) -> None:
        """Initialize enhanced authentication features."""
        if not ENHANCED_FEATURES_AVAILABLE:
            logger.warning("Enhanced authentication features not available - missing dependencies")
            return

        self.config = config

        # Initialize credential management
        if credential_store is None:
            if storage_path:
                credential_store = EncryptedFileStore(storage_path / "credentials")
            else:
                credential_store = InMemoryStore()

        self.credential_manager = CredentialManager(credential_store)

        # Initialize session management
        self.session_managers: Dict[str, SessionManager] = {}

        # Initialize retry handlers and circuit breakers
        self._retry_handlers: Dict[str, RetryHandler] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Initialize from enhanced configuration
        self._initialize_from_enhanced_config()

    def _initialize_from_enhanced_config(self) -> None:
        """Initialize authentication methods from enhanced configuration."""
        if not hasattr(self, 'config') or not self.config:
            return

        for method_name, method_config in self.config.methods.items():
            try:
                # Create auth method from enhanced config
                auth_method = self._create_auth_method_from_enhanced_config(method_config)
                self._auth_methods[method_name] = auth_method

                # Create retry handler and circuit breaker
                retry_policy = method_config.retry_policy
                circuit_breaker = CircuitBreaker(
                    failure_threshold=5,  # Could be configurable
                    recovery_timeout=60.0,
                    expected_exception=AuthenticationError
                )
                self._circuit_breakers[method_name] = circuit_breaker
                self._retry_handlers[method_name] = RetryHandler(retry_policy, circuit_breaker)

                # Create session manager
                session_config = method_config.session_config
                self.session_managers[method_name] = SessionManager(session_config)

                logger.debug(f"Initialized enhanced authentication method: {method_name}")

            except Exception as e:
                logger.error(f"Failed to initialize authentication method '{method_name}': {e}")

        # Set default method and URL patterns
        if hasattr(self.config, 'default_method') and self.config.default_method:
            self._default_method = self.config.default_method

        if hasattr(self.config, 'url_patterns'):
            self._url_patterns.update(self.config.url_patterns)

    def _create_auth_method_from_enhanced_config(self, config: "EnhancedAuthConfig") -> AuthMethod:
        """Create an authentication method from enhanced configuration."""
        # Convert enhanced config to legacy config for compatibility
        if config.auth_type == AuthType.API_KEY:
            legacy_config = APIKeyConfig(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                api_key=config.api_key.get_credential_value() or "",
                key_name=config.key_name,
                location=config.location,
                prefix=config.prefix
            )
            return APIKeyAuth(legacy_config)

        elif config.auth_type == AuthType.BASIC:
            legacy_config = BasicAuthConfig(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                username=config.username.get_credential_value() or "",
                password=config.password.get_credential_value() or ""
            )
            return BasicAuth(legacy_config)

        elif config.auth_type == AuthType.BEARER:
            legacy_config = BearerTokenConfig(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                token=config.token.get_credential_value() or "",
                token_prefix=config.token_prefix
            )
            return BearerTokenAuth(legacy_config)

        elif config.auth_type == AuthType.JWT:
            legacy_config = JWTConfig(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                secret_key=config.secret_key.get_credential_value() or "",
                algorithm=config.algorithm,
                issuer=config.issuer,
                audience=config.audience,
                expires_in=config.expires_in
            )
            return JWTAuth(legacy_config)

        elif config.auth_type == AuthType.OAUTH2:
            legacy_config = OAuth2Config(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                authorization_url=config.authorization_url,
                token_url=config.token_url,
                client_id=config.client_id.get_credential_value() or "",
                client_secret=config.client_secret.get_credential_value() or "",
                redirect_uri=config.redirect_uri,
                scopes=config.scopes
            )
            return OAuth2Auth(legacy_config)

        elif config.auth_type == AuthType.CUSTOM:
            # For custom auth, we need to resolve all credentials
            resolved_credentials = {}
            for cred_name, cred_config in config.credentials.items():
                resolved_credentials[cred_name] = cred_config.get_credential_value() or ""

            legacy_config = CustomAuthConfig(
                auth_type=config.auth_type,
                enabled=config.enabled,
                cache_credentials=config.cache_credentials,
                auto_refresh=config.auto_refresh,
                timeout=config.timeout,
                auth_method=config.auth_method,
                credentials=resolved_credentials,
                headers=config.custom_headers,
                params=config.custom_params
            )
            return CustomAuth(legacy_config)

        else:
            raise ValueError(f"Unsupported authentication type: {config.auth_type}")

    def add_auth_method(self, name: str, auth_method: AuthMethod) -> None:
        """
        Add an authentication method.

        Args:
            name: Unique name for the authentication method
            auth_method: Authentication method instance
        """
        self._auth_methods[name] = auth_method

        # Set as default if it's the first method
        if self._default_method is None:
            self._default_method = name

    def remove_auth_method(self, name: str) -> None:
        """
        Remove an authentication method.

        Args:
            name: Name of the authentication method to remove
        """
        if name in self._auth_methods:
            del self._auth_methods[name]

            # Update default if removed method was default
            if self._default_method == name:
                self._default_method = next(iter(self._auth_methods.keys()), None)

    def set_default_method(self, name: str) -> None:
        """
        Set the default authentication method.

        Args:
            name: Name of the authentication method to use as default

        Raises:
            AuthenticationError: If the method doesn't exist
        """
        if name not in self._auth_methods:
            raise AuthenticationError(f"Authentication method '{name}' not found")

        self._default_method = name

    def add_url_pattern(self, pattern: str, auth_method_name: str) -> None:
        """
        Associate a URL pattern with an authentication method.

        Args:
            pattern: URL pattern (simple string matching for now)
            auth_method_name: Name of the authentication method

        Raises:
            AuthenticationError: If the authentication method doesn't exist
        """
        if auth_method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{auth_method_name}' not found"
            )

        self._url_patterns[pattern] = auth_method_name

    def get_auth_method_for_url(self, url: str) -> Optional[str]:
        """
        Get the appropriate authentication method for a URL.

        Args:
            url: URL to check

        Returns:
            Authentication method name or None if no pattern matches
        """
        for pattern, method_name in self._url_patterns.items():
            if pattern in url:
                return method_name

        return self._default_method

    async def authenticate(
        self,
        method_name: Optional[str] = None,
        url: Optional[str] = None,
        force_refresh: bool = False,
        **kwargs: Any
    ) -> AuthResult:
        """
        Perform authentication using the specified or default method.

        Args:
            method_name: Name of the authentication method to use (uses default if None)
            url: URL for method selection (if method_name is None)
            force_refresh: Force refresh of credentials
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication data

        Raises:
            AuthenticationError: If authentication fails or method not found
        """
        # Determine authentication method
        if method_name is None:
            if url:
                method_name = self.get_auth_method_for_url(url)
            else:
                method_name = self._default_method

        if method_name is None:
            return AuthResult(success=True)  # No authentication configured

        if method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{method_name}' not found"
            )

        # Use enhanced authentication if available
        if self._enhanced_features_enabled and method_name in self._retry_handlers:
            return await self._authenticate_with_enhanced_features(
                method_name, force_refresh, **kwargs
            )

        # Fallback to basic authentication
        auth_method = self._auth_methods[method_name]
        return await auth_method.get_auth_data(force_refresh=force_refresh, **kwargs)

    async def _authenticate_with_enhanced_features(
        self,
        method_name: str,
        force_refresh: bool = False,
        **kwargs: Any
    ) -> AuthResult:
        """Perform authentication with enhanced features (retry, sessions, etc.)."""
        # Get components
        auth_method = self._auth_methods[method_name]
        retry_handler = self._retry_handlers[method_name]
        session_manager = self.session_managers.get(method_name)

        # Check for existing session if not forcing refresh
        if not force_refresh and session_manager:
            sessions = await session_manager.list_sessions(method_name)
            if sessions:
                # Use most recent active session
                latest_session = max(sessions, key=lambda s: s.last_accessed)
                if latest_session.auth_result and latest_session.auth_result.success:
                    await session_manager.refresh_session(latest_session.session_id)
                    logger.debug(f"Using cached session for {method_name}")
                    return latest_session.auth_result

        # Perform authentication with retry
        async def auth_operation():
            try:
                result = await auth_method.get_auth_data(force_refresh=force_refresh, **kwargs)

                # Create session for successful authentication
                if result.success and session_manager:
                    await session_manager.create_session(method_name, result)

                return result

            except Exception as e:
                # Classify and re-raise as AuthenticationError
                auth_error = classify_error(e)
                logger.error(f"Authentication failed for {method_name}: {auth_error}")
                raise auth_error

        try:
            result = await retry_handler.execute_with_retry(
                auth_operation,
                operation_name=f"authentication:{method_name}"
            )

            logger.info(f"Authentication successful for {method_name}")
            return result

        except Exception as e:
            if not isinstance(e, AuthenticationError):
                e = classify_error(e)
            logger.error(f"Authentication failed for {method_name} after retries: {e}")
            raise

    async def authenticate_for_url(self, url: str, **kwargs: Any) -> AuthResult:
        """
        Perform authentication for a specific URL.

        Args:
            url: URL to authenticate for
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication data
        """
        method_name = self.get_auth_method_for_url(url)
        return await self.authenticate(method_name, **kwargs)

    async def refresh(self, method_name: Optional[str] = None) -> AuthResult:
        """
        Refresh authentication for the specified or default method.

        Args:
            method_name: Name of the authentication method to refresh

        Returns:
            AuthResult with refreshed authentication data

        Raises:
            AuthenticationError: If refresh fails or method not found
        """
        if method_name is None:
            method_name = self._default_method

        if method_name is None:
            return AuthResult(success=True)

        if method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{method_name}' not found"
            )

        auth_method = self._auth_methods[method_name]
        return await auth_method.refresh()

    def clear_cache(self, method_name: Optional[str] = None) -> None:
        """
        Clear cached authentication data.

        Args:
            method_name: Name of the method to clear cache for (clears all if None)
        """
        if method_name is None:
            # Clear cache for all methods
            for auth_method in self._auth_methods.values():
                auth_method.clear_cache()
        else:
            if method_name in self._auth_methods:
                self._auth_methods[method_name].clear_cache()

    def list_methods(self) -> List[str]:
        """
        Get list of available authentication method names.

        Returns:
            List of authentication method names
        """
        return list(self._auth_methods.keys())

    def get_method_info(self, method_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an authentication method.

        Args:
            method_name: Name of the authentication method

        Returns:
            Dictionary with method information or None if not found
        """
        if method_name not in self._auth_methods:
            return None

        auth_method = self._auth_methods[method_name]
        info = {
            "name": method_name,
            "type": auth_method.config.auth_type.value,
            "enabled": auth_method.config.enabled,
            "auto_refresh": auth_method.config.auto_refresh,
            "cache_credentials": auth_method.config.cache_credentials,
        }

        # Add enhanced features info if available
        if self._enhanced_features_enabled:
            if method_name in self._circuit_breakers:
                circuit_breaker = self._circuit_breakers[method_name]
                info.update({
                    "circuit_breaker_state": circuit_breaker.state.value,
                    "failure_count": circuit_breaker.failure_count,
                    "healthy": circuit_breaker.state.value != "open"
                })

            if method_name in self.session_managers:
                sessions = asyncio.create_task(self.session_managers[method_name].list_sessions(method_name))
                # Note: This is a sync method, so we can't await here
                # In practice, you'd want to make this async or provide a separate async method
                info["has_session_manager"] = True

        return info

    # Enhanced methods (available when enhanced features are enabled)

    async def refresh_credentials(self, method_name: str) -> AuthResult:
        """
        Refresh credentials for a specific authentication method.

        Args:
            method_name: Authentication method name

        Returns:
            Refreshed authentication result
        """
        return await self.authenticate(method_name, force_refresh=True)

    async def get_session_info(self, method_name: str) -> List["SessionInfo"]:
        """
        Get session information for an authentication method.

        Args:
            method_name: Authentication method name

        Returns:
            List of active sessions
        """
        if not self._enhanced_features_enabled or method_name not in self.session_managers:
            return []

        return await self.session_managers[method_name].list_sessions(method_name)

    async def cleanup_sessions(self, method_name: Optional[str] = None) -> int:
        """
        Clean up expired sessions.

        Args:
            method_name: Specific method to clean up (all if None)

        Returns:
            Number of sessions cleaned up
        """
        if not self._enhanced_features_enabled:
            return 0

        total_cleaned = 0

        if method_name:
            if method_name in self.session_managers:
                total_cleaned = await self.session_managers[method_name].cleanup_sessions(method_name)
        else:
            for session_manager in self.session_managers.values():
                total_cleaned += await session_manager.cleanup_sessions()

        logger.info(f"Cleaned up {total_cleaned} expired sessions")
        return total_cleaned

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of all authentication methods.

        Returns:
            Health status information
        """
        status = {
            "overall_healthy": True,
            "methods": {},
            "enhanced_features_enabled": self._enhanced_features_enabled,
            "timestamp": asyncio.get_event_loop().time() if self._enhanced_features_enabled else None
        }

        for method_name in self._auth_methods.keys():
            method_status = {"healthy": True}

            if self._enhanced_features_enabled and method_name in self._circuit_breakers:
                circuit_breaker = self._circuit_breakers[method_name]
                sessions = await self.get_session_info(method_name)

                method_status.update({
                    "circuit_breaker_state": circuit_breaker.state.value,
                    "failure_count": circuit_breaker.failure_count,
                    "active_sessions": len(sessions),
                    "healthy": circuit_breaker.state.value != "open"
                })

            status["methods"][method_name] = method_status

            if not method_status["healthy"]:
                status["overall_healthy"] = False

        return status

    async def shutdown(self) -> None:
        """Shutdown the authentication manager and cleanup resources."""
        if not self._enhanced_features_enabled:
            return

        logger.info("Shutting down authentication manager")

        # Shutdown session managers
        for session_manager in self.session_managers.values():
            await session_manager.shutdown()

        # Final cleanup
        await self.cleanup_sessions()

        logger.info("Authentication manager shutdown complete")

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> "AuthManager":
        """
        Create an AuthManager from configuration dictionary.

        Args:
            config: Configuration dictionary with auth method definitions

        Returns:
            Configured AuthManager instance

        Example config:
            ```python
            config = {
                "methods": {
                    "api_key": {
                        "type": "api_key",
                        "api_key": "your-key",
                        "key_name": "X-API-Key"
                    },
                    "oauth": {
                        "type": "oauth2",
                        "token_url": "https://api.example.com/token",
                        "client_id": "client-id",
                        "client_secret": "client-secret"
                    }
                },
                "default": "api_key",
                "url_patterns": {
                    "api.example.com": "oauth",
                    "legacy.example.com": "api_key"
                }
            }
            ```
        """
        manager = cls()

        # Create authentication methods
        methods_config = config.get("methods", {})
        for name, method_config in methods_config.items():
            auth_type = method_config.get("type")

            auth_method: AuthMethod
            if auth_type == "api_key":
                auth_config = APIKeyConfig(**method_config)
                auth_method = APIKeyAuth(auth_config)
            elif auth_type == "oauth2":
                oauth_config = OAuth2Config(**method_config)
                auth_method = OAuth2Auth(oauth_config)
            elif auth_type == "jwt":
                jwt_config = JWTConfig(**method_config)
                auth_method = JWTAuth(jwt_config)
            elif auth_type == "basic":
                basic_config = BasicAuthConfig(**method_config)
                auth_method = BasicAuth(basic_config)
            elif auth_type == "bearer":
                bearer_config = BearerTokenConfig(**method_config)
                auth_method = BearerTokenAuth(bearer_config)
            elif auth_type == "custom":
                custom_config = CustomAuthConfig(**method_config)
                auth_method = CustomAuth(custom_config)
            else:
                raise AuthenticationError(
                    f"Unsupported authentication type: {auth_type}"
                )

            manager.add_auth_method(name, auth_method)

        # Set default method
        default_method = config.get("default")
        if default_method:
            manager.set_default_method(default_method)

        # Add URL patterns
        url_patterns = config.get("url_patterns", {})
        for pattern, method_name in url_patterns.items():
            manager.add_url_pattern(pattern, method_name)

        return manager

    @classmethod
    def from_config_file(
        cls,
        config_path: Path,
        storage_path: Optional[Path] = None,
        enable_enhanced_features: bool = True
    ) -> "AuthManager":
        """
        Create manager from configuration file.

        Args:
            config_path: Path to configuration file
            storage_path: Path for storage (defaults to config file directory)
            enable_enhanced_features: Whether to enable enhanced features

        Returns:
            Configured authentication manager
        """
        if not ENHANCED_FEATURES_AVAILABLE or not enable_enhanced_features:
            # Fallback to basic configuration loading
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
            return cls.create_from_config(config_dict)

        import yaml

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Load configuration
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                config_dict = yaml.safe_load(f)
            else:
                config_dict = json.load(f)

        enhanced_config = AuthenticationConfig.from_dict(config_dict)

        # Use config file directory as default storage path
        if storage_path is None:
            storage_path = config_path.parent / "auth_storage"

        return cls(
            enhanced_config=enhanced_config,
            storage_path=storage_path,
            enable_enhanced_features=enable_enhanced_features
        )

    @classmethod
    def from_environment(
        cls,
        prefix: str = "WEBFETCH_AUTH_",
        storage_path: Optional[Path] = None,
        enable_enhanced_features: bool = True
    ) -> "AuthManager":
        """
        Create manager from environment variables.

        Args:
            prefix: Environment variable prefix
            storage_path: Path for storage
            enable_enhanced_features: Whether to enable enhanced features

        Returns:
            Configured authentication manager
        """
        if not ENHANCED_FEATURES_AVAILABLE or not enable_enhanced_features:
            logger.warning("Enhanced features not available - using basic configuration")
            return cls()

        enhanced_config = AuthenticationConfig.from_environment(prefix)
        return cls(
            enhanced_config=enhanced_config,
            storage_path=storage_path,
            enable_enhanced_features=enable_enhanced_features
        )
