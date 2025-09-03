"""
Security utilities for web_fetch HTTP components.

This module provides comprehensive security features including SSRF protection,
URL validation, and security-focused request handling.
"""

import ipaddress
import re
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, Field, validator

from ..exceptions import WebFetchError


class SSRFProtectionConfig(BaseModel):
    """Configuration for SSRF protection."""
    
    # URL scheme restrictions
    allowed_schemes: Set[str] = Field(
        default={'http', 'https'},
        description="Allowed URL schemes"
    )
    
    # Host restrictions
    blocked_hosts: Set[str] = Field(
        default_factory=lambda: {
            'localhost', '127.0.0.1', '::1',
            '0.0.0.0', '169.254.169.254',  # AWS metadata
            '100.64.0.0/10',  # Carrier-grade NAT
        },
        description="Blocked hostnames and IP ranges"
    )
    
    allowed_hosts: Optional[Set[str]] = Field(
        default=None,
        description="Allowed hostnames (if set, only these are allowed)"
    )
    
    # IP range restrictions
    blocked_ip_ranges: List[str] = Field(
        default_factory=lambda: [
            '10.0.0.0/8',      # Private networks
            '172.16.0.0/12',   # Private networks
            '192.168.0.0/16',  # Private networks
            '127.0.0.0/8',     # Loopback
            '169.254.0.0/16',  # Link-local
            '224.0.0.0/4',     # Multicast
            '240.0.0.0/4',     # Reserved
            '::1/128',         # IPv6 loopback
            'fc00::/7',        # IPv6 private
            'fe80::/10',       # IPv6 link-local
        ],
        description="Blocked IP address ranges"
    )
    
    allowed_ip_ranges: Optional[List[str]] = Field(
        default=None,
        description="Allowed IP ranges (if set, only these are allowed)"
    )
    
    # Port restrictions
    blocked_ports: Set[int] = Field(
        default_factory=lambda: {
            22, 23, 25, 53, 110, 143, 993, 995,  # Common services
            3306, 5432, 6379, 27017,             # Databases
            8080, 8443, 9200, 9300,              # Common internal services
        },
        description="Blocked port numbers"
    )
    
    allowed_ports: Optional[Set[int]] = Field(
        default=None,
        description="Allowed ports (if set, only these are allowed)"
    )
    
    # Additional security settings
    max_redirects: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of redirects to follow"
    )
    
    validate_certificates: bool = Field(
        default=True,
        description="Validate SSL certificates"
    )
    
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Request timeout in seconds"
    )
    
    user_agent_required: bool = Field(
        default=True,
        description="Require User-Agent header"
    )


class URLValidator:
    """Validates URLs against SSRF attacks and security policies."""
    
    def __init__(self, config: Optional[SSRFProtectionConfig] = None):
        """
        Initialize URL validator.
        
        Args:
            config: SSRF protection configuration
        """
        self.config = config or SSRFProtectionConfig()
        self._compiled_ip_ranges = self._compile_ip_ranges()
    
    def _compile_ip_ranges(self) -> Dict[str, List[Any]]:
        """Compile IP ranges for efficient checking."""
        compiled: Dict[str, List[Any]] = {
            'blocked': [],
            'allowed': []
        }
        
        # Compile blocked ranges
        for range_str in self.config.blocked_ip_ranges:
            try:
                compiled['blocked'].append(ipaddress.ip_network(range_str, strict=False))
            except ValueError:
                continue
        
        # Compile allowed ranges
        if self.config.allowed_ip_ranges:
            for range_str in self.config.allowed_ip_ranges:
                try:
                    compiled['allowed'].append(ipaddress.ip_network(range_str, strict=False))
                except ValueError:
                    continue
        
        return compiled
    
    def validate_url(self, url: str) -> str:
        """
        Validate URL against SSRF protection rules.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated and normalized URL
            
        Raises:
            WebFetchError: If URL violates security policy
        """
        if not url or not isinstance(url, str):
            raise WebFetchError("Invalid URL: URL must be a non-empty string")
        
        # Parse URL
        try:
            parsed = urlparse(url.strip())
        except Exception as e:
            raise WebFetchError(f"Invalid URL format: {e}")
        
        # Validate scheme
        if parsed.scheme.lower() not in self.config.allowed_schemes:
            raise WebFetchError(
                f"Blocked URL scheme: {parsed.scheme}. "
                f"Allowed schemes: {', '.join(self.config.allowed_schemes)}"
            )
        
        # Validate hostname
        if not parsed.hostname:
            raise WebFetchError("Invalid URL: Missing hostname")
        
        hostname = parsed.hostname.lower()
        
        # Check blocked hosts
        if hostname in self.config.blocked_hosts:
            raise WebFetchError(f"Blocked hostname: {hostname}")
        
        # Check allowed hosts (if configured)
        if self.config.allowed_hosts and hostname not in self.config.allowed_hosts:
            raise WebFetchError(f"Hostname not in allowlist: {hostname}")
        
        # Validate IP address
        self._validate_ip_address(hostname)
        
        # Validate port
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme.lower() == 'https' else 80
        
        if port in self.config.blocked_ports:
            raise WebFetchError(f"Blocked port: {port}")
        
        if self.config.allowed_ports and port not in self.config.allowed_ports:
            raise WebFetchError(f"Port not in allowlist: {port}")
        
        # Validate path for suspicious patterns
        self._validate_path(parsed.path)
        
        # Return normalized URL
        return urlunparse(parsed)
    
    def _validate_ip_address(self, hostname: str) -> None:
        """Validate IP address against blocked/allowed ranges."""
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            # Not an IP address, skip IP validation
            return
        
        # Check blocked ranges
        for blocked_range in self._compiled_ip_ranges['blocked']:
            if ip in blocked_range:
                raise WebFetchError(f"Blocked IP address: {hostname} (in range {blocked_range})")
        
        # Check allowed ranges (if configured)
        if self._compiled_ip_ranges['allowed']:
            allowed = False
            for allowed_range in self._compiled_ip_ranges['allowed']:
                if ip in allowed_range:
                    allowed = True
                    break
            
            if not allowed:
                raise WebFetchError(f"IP address not in allowlist: {hostname}")
    
    def _validate_path(self, path: str) -> None:
        """Validate URL path for suspicious patterns."""
        if not path:
            return
        
        # Check for path traversal attempts
        suspicious_patterns = [
            '../', '..\\',  # Path traversal
            '%2e%2e%2f', '%2e%2e%5c',  # URL-encoded path traversal
            '/./', '/.//',  # Current directory references
            '//', '\\\\',   # Double slashes
        ]
        
        path_lower = path.lower()
        for pattern in suspicious_patterns:
            if pattern in path_lower:
                raise WebFetchError(f"Suspicious path pattern detected: {pattern}")
        
        # Check for encoded null bytes and control characters
        if '%00' in path or any(ord(c) < 32 for c in path if c not in '\t\n\r'):
            raise WebFetchError("Path contains invalid characters")
    
    def validate_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Validate and sanitize request headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Validated headers
            
        Raises:
            WebFetchError: If headers violate security policy
        """
        if not headers:
            headers = {}
        
        validated_headers = {}
        
        # Check for required User-Agent
        if self.config.user_agent_required:
            user_agent = headers.get('User-Agent') or headers.get('user-agent')
            if not user_agent:
                raise WebFetchError("User-Agent header is required")
        
        # Validate each header
        for name, value in headers.items():
            # Validate header name
            if not self._is_valid_header_name(name):
                raise WebFetchError(f"Invalid header name: {name}")
            
            # Validate header value
            if not self._is_valid_header_value(str(value)):
                raise WebFetchError(f"Invalid header value for {name}")
            
            # Check for security-sensitive headers
            name_lower = name.lower()
            if name_lower in ['host', 'authorization', 'cookie']:
                # These headers need special validation
                self._validate_sensitive_header(name_lower, str(value))
            
            validated_headers[name] = str(value)
        
        return validated_headers
    
    def _is_valid_header_name(self, name: str) -> bool:
        """Check if header name is valid."""
        if not name or not isinstance(name, str):
            return False
        
        # RFC 7230: header names are tokens
        return re.match(r'^[!#$%&\'*+\-.0-9A-Z^_`a-z|~]+$', name) is not None
    
    def _is_valid_header_value(self, value: str) -> bool:
        """Check if header value is valid."""
        if not isinstance(value, str):
            return False
        
        # Check for control characters (except tab)
        return not any(ord(c) < 32 and c != '\t' for c in value)
    
    def _validate_sensitive_header(self, name: str, value: str) -> None:
        """Validate security-sensitive headers."""
        if name == 'host':
            # Validate Host header to prevent host header injection
            if not re.match(r'^[a-zA-Z0-9.-]+(?::[0-9]+)?$', value):
                raise WebFetchError(f"Invalid Host header: {value}")
        
        elif name == 'authorization':
            # Basic validation for Authorization header
            if len(value) > 8192:  # Reasonable limit
                raise WebFetchError("Authorization header too long")
        
        elif name == 'cookie':
            # Basic validation for Cookie header
            if len(value) > 4096:  # Reasonable limit
                raise WebFetchError("Cookie header too long")


class SecurityMiddleware:
    """Security middleware for HTTP requests."""
    
    def __init__(self, config: Optional[SSRFProtectionConfig] = None):
        """
        Initialize security middleware.
        
        Args:
            config: SSRF protection configuration
        """
        self.validator = URLValidator(config)
        self.config = config or SSRFProtectionConfig()
    
    async def validate_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> tuple[str, Dict[str, str]]:
        """
        Validate HTTP request for security compliance.
        
        Args:
            url: Request URL
            headers: Request headers
            
        Returns:
            Tuple of (validated_url, validated_headers)
            
        Raises:
            WebFetchError: If request violates security policy
        """
        # Validate URL
        validated_url = self.validator.validate_url(url)
        
        # Validate headers
        validated_headers = self.validator.validate_headers(headers or {})
        
        return validated_url, validated_headers
