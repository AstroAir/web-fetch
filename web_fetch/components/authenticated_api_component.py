"""
Authenticated API resource component.

This component extends HTTP functionality with integrated authentication
support for OAuth, API keys, JWT tokens, and other authentication methods.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..auth import (
    APIKeyAuth, APIKeyConfig,
    AuthManager, AuthMethod,
    BasicAuth, BasicAuthConfig,
    BearerTokenAuth, BearerTokenConfig,
    JWTAuth, JWTConfig,
    OAuth2Auth, OAuth2Config,
)
from ..models.extended_resources import AuthenticatedAPIConfig
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .http_component import HTTPResourceComponent
from .base import component_registry

logger = logging.getLogger(__name__)


class AuthenticatedAPIComponent(HTTPResourceComponent):
    """
    Resource component for authenticated API endpoints.

    This component extends HTTP functionality with integrated authentication support
    for multiple authentication methods including OAuth 2.0, API keys, JWT tokens,
    Basic authentication, and Bearer tokens. It handles automatic token management,
    refresh, and retry logic for authentication failures.

    Features:
        - Multiple authentication methods (OAuth 2.0, API Key, JWT, Basic, Bearer)
        - Automatic token refresh and management
        - Retry logic for authentication failures
        - Secure credential handling
        - Request/response logging and monitoring
        - Integration with existing HTTP functionality

    Example:
        OAuth 2.0 authentication:

        ```python
        from web_fetch.components.authenticated_api_component import AuthenticatedAPIComponent
        from web_fetch.models.extended_resources import AuthenticatedAPIConfig
        from web_fetch.models.resource import ResourceRequest, ResourceKind
        from pydantic import AnyUrl

        # Configure OAuth 2.0 authentication
        api_config = AuthenticatedAPIConfig(
            auth_method="oauth2",
            auth_config={
                "token_url": "https://api.example.com/oauth/token",
                "client_id": "your-client-id",
                "client_secret": "your-client-secret",
                "grant_type": "client_credentials",
                "scope": "read write"
            },
            retry_on_auth_failure=True,
            refresh_token_threshold=300
        )

        component = AuthenticatedAPIComponent(api_config=api_config)

        # Create API request
        request = ResourceRequest(
            uri=AnyUrl("https://api.example.com/data"),
            kind=ResourceKind.API_AUTH,
            headers={"Accept": "application/json"}
        )

        # Fetch with automatic authentication
        result = await component.fetch(request)

        if result.is_success:
            api_data = result.content
            auth_info = result.metadata["authentication"]
            print(f"Authenticated: {auth_info['authenticated']}")
            print(f"Data: {api_data}")
        ```

        API Key authentication:

        ```python
        # Configure API Key authentication
        api_config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": "your-api-key",
                "key_name": "X-API-Key",
                "location": "header",
                "prefix": "Bearer"
            }
        )

        component = AuthenticatedAPIComponent(api_config=api_config)
        ```

    Attributes:
        kind (ResourceKind): Always ResourceKind.API_AUTH
        api_config (AuthenticatedAPIConfig): Authentication configuration
        auth_manager (AuthManager): Authentication method manager
    """

    kind = ResourceKind.API_AUTH

    def __init__(
        self,
        config: Optional[ResourceConfig] = None,
        api_config: Optional[AuthenticatedAPIConfig] = None
    ) -> None:
        """
        Initialize authenticated API component.

        Args:
            config: Base resource configuration for caching and validation.
                   If None, uses default configuration.
            api_config: Authentication configuration specifying the auth method
                       and credentials. If None, uses default API key configuration.

        Example:
            ```python
            from web_fetch.models.resource import ResourceConfig
            from web_fetch.models.extended_resources import AuthenticatedAPIConfig

            # Basic setup with OAuth 2.0
            api_config = AuthenticatedAPIConfig(
                auth_method="oauth2",
                auth_config={
                    "token_url": "https://api.example.com/oauth/token",
                    "client_id": "your-client-id",
                    "client_secret": "your-client-secret",
                    "grant_type": "client_credentials"
                }
            )

            component = AuthenticatedAPIComponent(
                config=ResourceConfig(enable_cache=True),
                api_config=api_config
            )
            ```
        """
        super().__init__(config)
        self.api_config = api_config or AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": "default-key",
                "key_name": "X-API-Key",
                "location": "header"
            }
        )
        self.auth_manager = AuthManager()
        self._auth_method: Optional[AuthMethod] = None
        self._last_auth_time: Optional[float] = None
        self._setup_authentication()
    
    def _setup_authentication(self) -> None:
        """Setup authentication method based on configuration."""
        try:
            auth_method = self.api_config.auth_method.lower()
            auth_config = self.api_config.auth_config
            
            if auth_method == "oauth2":
                oauth_config = OAuth2Config(**auth_config)
                self._auth_method = OAuth2Auth(oauth_config)
            elif auth_method == "api_key":
                api_key_config = APIKeyConfig(**auth_config)
                self._auth_method = APIKeyAuth(api_key_config)
            elif auth_method == "jwt":
                jwt_config = JWTConfig(**auth_config)
                self._auth_method = JWTAuth(jwt_config)
            elif auth_method == "basic":
                basic_config = BasicAuthConfig(**auth_config)
                self._auth_method = BasicAuth(basic_config)
            elif auth_method == "bearer":
                bearer_config = BearerTokenConfig(**auth_config)
                self._auth_method = BearerTokenAuth(bearer_config)
            else:
                raise ValueError(f"Unsupported authentication method: {auth_method}")
            
            # Register with auth manager
            self.auth_manager.add_auth_method("default", self._auth_method)
            
        except Exception as e:
            logger.error(f"Failed to setup authentication: {e}")
            raise
    
    async def _apply_authentication(self, request: ResourceRequest) -> ResourceRequest:
        """
        Apply authentication to the request.
        
        Args:
            request: Original resource request
            
        Returns:
            Modified request with authentication applied
        """
        try:
            # Check if we need to refresh authentication
            current_time = time.time()
            should_refresh = (
                self._last_auth_time is None or
                (current_time - self._last_auth_time) > self.api_config.refresh_token_threshold
            )
            
            if should_refresh:
                # Authenticate
                auth_result = await self.auth_manager.authenticate("default")
                
                if not auth_result.success:
                    raise Exception(f"Authentication failed: {auth_result.error}")
                
                self._last_auth_time = current_time
            else:
                # Use cached authentication
                auth_result = await self.auth_manager.authenticate("default")
            
            # Apply authentication data to request
            modified_request = request.model_copy(deep=True)
            
            # Merge headers
            if auth_result.headers:
                if modified_request.headers is None:
                    modified_request.headers = {}
                modified_request.headers.update(auth_result.headers)
            
            # Add base headers
            if self.api_config.base_headers:
                if modified_request.headers is None:
                    modified_request.headers = {}
                # Base headers go first, auth headers can override
                base_headers = self.api_config.base_headers.copy()
                base_headers.update(modified_request.headers)
                modified_request.headers = base_headers
            
            # Merge query parameters
            if auth_result.params:
                if modified_request.params is None:
                    modified_request.params = {}
                modified_request.params.update(auth_result.params)
            
            # Merge body data (for form-based auth)
            if auth_result.body_data:
                if "data" not in modified_request.options:
                    modified_request.options["data"] = {}
                if isinstance(modified_request.options["data"], dict):
                    modified_request.options["data"].update(auth_result.body_data)
            
            return modified_request
            
        except Exception as e:
            logger.error(f"Failed to apply authentication: {e}")
            raise
    
    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """
        Fetch authenticated API endpoint.
        
        Args:
            request: Resource request with API endpoint and options
            
        Returns:
            ResourceResult with API response
        """
        try:
            # Apply authentication to request
            authenticated_request = await self._apply_authentication(request)
            
            # Use parent HTTP component to make the request
            result = await super().fetch(authenticated_request)
            
            # Handle authentication failures
            if result.status_code in [401, 403] and self.api_config.retry_on_auth_failure:
                logger.info("Authentication failure detected, retrying with fresh auth")
                
                # Clear cached auth and retry
                self._last_auth_time = None
                if self._auth_method:
                    self._auth_method.clear_cache()
                
                # Retry with fresh authentication
                authenticated_request = await self._apply_authentication(request)
                result = await super().fetch(authenticated_request)
            
            # Add authentication metadata
            if "authentication" not in result.metadata:
                result.metadata["authentication"] = {}
            
            result.metadata["authentication"].update({
                "method": self.api_config.auth_method,
                "authenticated": True,
                "retry_attempted": result.status_code in [401, 403],
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch authenticated API: {e}")
            return ResourceResult(
                url=str(request.uri),
                error=f"Authenticated API fetch error: {str(e)}",
                metadata={
                    "authentication": {
                        "method": self.api_config.auth_method,
                        "authenticated": False,
                        "error": str(e),
                    }
                }
            )
    
    async def validate(self, result: ResourceResult) -> ResourceResult:
        """
        Validate authenticated API result.
        
        Args:
            result: Resource result to validate
            
        Returns:
            Validated resource result
        """
        # First run parent HTTP validation
        result = await super().validate(result)
        
        if result.error:
            return result
        
        try:
            # Add API-specific validation
            if "validation" not in result.metadata:
                result.metadata["validation"] = {}
            
            # Check for common API error patterns
            api_validation = {
                "is_authenticated": result.status_code not in [401, 403] if result.status_code else False,
                "is_api_error": result.status_code >= 400 if result.status_code else False,
                "has_rate_limit_headers": any(
                    header.lower().startswith(('x-ratelimit', 'x-rate-limit', 'ratelimit'))
                    for header in result.headers.keys()
                ),
            }
            
            # Check for API-specific error responses
            if isinstance(result.content, dict):
                api_validation.update({
                    "has_error_field": "error" in result.content or "errors" in result.content,
                    "has_message_field": "message" in result.content or "msg" in result.content,
                })
            
            result.metadata["validation"]["api"] = api_validation
            
            return result
            
        except Exception as e:
            logger.error(f"API validation error: {e}")
            result.error = f"API validation failed: {str(e)}"
            return result
    
    def cache_key(self, request: ResourceRequest) -> Optional[str]:
        """
        Generate cache key for authenticated API request.
        
        Args:
            request: Resource request
            
        Returns:
            Cache key string or None
        """
        if not self.config or not self.config.enable_cache:
            return None
        
        # For authenticated APIs, include auth method in cache key
        # but be careful not to include sensitive auth data
        key_parts = [
            "api_auth",
            str(request.uri),
            self.api_config.auth_method,
            str(request.options.get("method", "GET")),
        ]
        
        # Include non-sensitive parameters
        if request.params:
            sorted_params = sorted(request.params.items())
            key_parts.append(str(sorted_params))
        
        return ":".join(key_parts)


# Register component in the global registry
component_registry.register(
    ResourceKind.API_AUTH, 
    lambda config=None: AuthenticatedAPIComponent(config)
)

__all__ = ["AuthenticatedAPIComponent"]
