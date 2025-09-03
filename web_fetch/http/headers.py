"""
Enhanced header management for web_fetch.

This module provides comprehensive header management with presets,
validation, and intelligent header handling.
"""

import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, unquote

from pydantic import BaseModel, Field

from .security import SecurityMiddleware, SSRFProtectionConfig


class HeaderPresets:
    """Common header presets for different scenarios."""

    # Browser-like headers
    BROWSER_CHROME = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    BROWSER_FIREFOX = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # API headers
    API_JSON = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "WebFetch/1.0",
    }

    API_XML = {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "User-Agent": "WebFetch/1.0",
    }

    # Mobile headers
    MOBILE_ANDROID = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    MOBILE_IOS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }


class HeaderRule(BaseModel):
    """Rule for header management."""

    pattern: str = Field(description="URL pattern (regex)")
    headers: Dict[str, str] = Field(description="Headers to apply")
    action: str = Field(default="add", description="Action: add, replace, remove")
    priority: int = Field(default=0, description="Rule priority")


class HeaderManager:
    """Advanced header management with rules and validation."""

    def __init__(
        self,
        security_config: Optional[SSRFProtectionConfig] = None,
        enable_security: bool = True
    ) -> None:
        """
        Initialize header manager.

        Args:
            security_config: Security configuration for validation
            enable_security: Enable security features
        """
        self._rules: List[HeaderRule] = []
        self._global_headers: Dict[str, str] = {}
        self._sensitive_headers: Set[str] = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "proxy-authorization",
            "www-authenticate",
            "x-forwarded-for",
            "x-real-ip",
            "x-forwarded-host",
        }

        # Security features
        self._enable_security = enable_security
        self._security_middleware = SecurityMiddleware(security_config) if enable_security else None

        # Injection attack patterns
        self._injection_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',               # JavaScript protocol
            r'vbscript:',                # VBScript protocol
            r'data:.*base64',            # Data URLs with base64
            r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',  # Control characters
            r'%[0-9a-fA-F]{2}',          # URL encoding (suspicious in headers)
        ]
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self._injection_patterns]

    def add_global_headers(self, headers: Dict[str, str]) -> None:
        self._global_headers.update(headers)

    def remove_global_header(self, header_name: str) -> None:
        self._global_headers.pop(header_name.lower(), None)

    def add_rule(self, rule: HeaderRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, pattern: str) -> None:
        self._rules = [rule for rule in self._rules if rule.pattern != pattern]

    def apply_headers(
        self, url: str, base_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        headers = self._global_headers.copy()
        if base_headers:
            headers.update(base_headers)
        for rule in self._rules:
            if re.match(rule.pattern, url):
                if rule.action == "add":
                    headers.update(rule.headers)
                elif rule.action == "replace":
                    headers.clear()
                    headers.update(rule.headers)
                elif rule.action == "remove":
                    for header_name in rule.headers:
                        headers.pop(header_name.lower(), None)
        return headers

    def validate_headers(self, headers: Dict[str, Any]) -> List[str]:
        """
        Validate headers with enhanced security checks.

        Args:
            headers: Headers to validate

        Returns:
            List of validation issues
        """
        issues: List[str] = []

        for name, value in headers.items():
            # Check header name format (RFC 7230 compliant)
            if not self._is_valid_header_name(name):
                issues.append(f"Invalid header name format: {name}")

            # Check for sensitive headers in logs
            if name.lower() in self._sensitive_headers:
                issues.append(f"Sensitive header detected: {name}")

            # Normalize to string for further checks
            str_value = str(value)
            if not isinstance(value, str):
                issues.append(f"Header value must be string: {name}")

            # Enhanced security validation
            if self._enable_security:
                security_issues = self._validate_header_security(name, str_value)
                issues.extend(security_issues)

        return issues

    def _is_valid_header_name(self, name: str) -> bool:
        """Check if header name is RFC 7230 compliant."""
        if not name or not isinstance(name, str):
            return False

        # RFC 7230: header names are tokens
        return re.match(r'^[!#$%&\'*+\-.0-9A-Z^_`a-z|~]+$', name) is not None

    def _validate_header_security(self, name: str, value: str) -> List[str]:
        """Perform security validation on header value."""
        issues: List[str] = []

        # Check for control characters (except tab)
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1f\x7f]", value):
            issues.append(f"Header value contains control characters: {name}")

        # Check for injection attack patterns
        for pattern in self._compiled_patterns:
            if pattern.search(value):
                issues.append(f"Potential injection attack in header {name}")
                break

        # Check header-specific security rules
        name_lower = name.lower()
        if name_lower == 'host':
            if not self._validate_host_header(value):
                issues.append(f"Invalid Host header value: {value}")
        elif name_lower == 'referer':
            if not self._validate_referer_header(value):
                issues.append(f"Invalid Referer header value: {value}")
        elif name_lower in ['x-forwarded-for', 'x-real-ip']:
            if not self._validate_ip_header(value):
                issues.append(f"Invalid IP header value: {value}")

        # Check for excessively long headers
        if len(value) > 8192:  # 8KB limit
            issues.append(f"Header value too long: {name}")

        return issues

    def _validate_host_header(self, value: str) -> bool:
        """Validate Host header to prevent host header injection."""
        # Basic format: hostname[:port]
        return re.match(r'^[a-zA-Z0-9.-]+(?::[0-9]+)?$', value) is not None

    def _validate_referer_header(self, value: str) -> bool:
        """Validate Referer header."""
        if not value:
            return True  # Empty referer is valid

        # Must be a valid URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(value)
            return bool(parsed.scheme in ['http', 'https'] and parsed.netloc)
        except Exception:
            return False

    def _validate_ip_header(self, value: str) -> bool:
        """Validate IP address headers."""
        # Can contain multiple IPs separated by commas
        ips = [ip.strip() for ip in value.split(',')]

        for ip in ips:
            if not self._is_valid_ip(ip):
                return False

        return True

    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is a valid IP address."""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize headers by removing invalid characters and values.

        Args:
            headers: Headers to sanitize

        Returns:
            Sanitized headers dictionary
        """
        sanitized: Dict[str, str] = {}

        for name, value in headers.items():
            # Skip invalid header names
            if not self._is_valid_header_name(name):
                continue

            str_value = str(value)

            # Remove control characters (except tab)
            clean_value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1f\x7f]", "", str_value)

            # Remove potential injection patterns if security is enabled
            if self._enable_security:
                for pattern in self._compiled_patterns:
                    clean_value = pattern.sub("", clean_value)

            # Trim whitespace
            clean_value = clean_value.strip()

            # Skip empty values
            if not clean_value:
                continue

            # Truncate excessively long headers
            if len(clean_value) > 8192:
                clean_value = clean_value[:8192]

            sanitized[name] = clean_value

        return sanitized

    async def validate_and_sanitize(self, headers: Dict[str, Any]) -> tuple[Dict[str, str], List[str]]:
        """
        Validate and sanitize headers in one operation.

        Args:
            headers: Headers to process

        Returns:
            Tuple of (sanitized_headers, validation_issues)
        """
        # Use security middleware if available
        if self._security_middleware:
            try:
                _, validated_headers = await self._security_middleware.validate_request("", headers)
                issues = []
            except Exception as e:
                validated_headers = headers
                issues = [str(e)]
        else:
            validated_headers = headers
            issues = self.validate_headers(headers)

        # Sanitize the headers
        sanitized_headers = self.sanitize_headers(validated_headers)

        return sanitized_headers, issues

    def get_headers_for_domain(self, domain: str) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for rule in self._rules:
            if domain in rule.pattern or re.match(rule.pattern, f"https://{domain}"):
                if rule.action == "add":
                    headers.update(rule.headers)
        return headers

    def merge_headers(self, *header_dicts: Dict[str, str]) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for headers in header_dicts:
            if headers:
                merged.update(headers)
        return merged

    def get_preset_headers(self, preset_name: str) -> Dict[str, str]:
        presets: Dict[str, Dict[str, str]] = {
            "browser_chrome": HeaderPresets.BROWSER_CHROME,
            "browser_firefox": HeaderPresets.BROWSER_FIREFOX,
            "api_json": HeaderPresets.API_JSON,
            "api_xml": HeaderPresets.API_XML,
            "mobile_android": HeaderPresets.MOBILE_ANDROID,
            "mobile_ios": HeaderPresets.MOBILE_IOS,
            "security": HeaderPresets.SECURITY_HEADERS,
        }
        if preset_name not in presets:
            raise ValueError(f"Unknown header preset: {preset_name}")
        return presets[preset_name].copy()

    def analyze_response_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        lower_headers: Dict[str, str] = {k.lower(): v for k, v in headers.items()}
        analysis: Dict[str, Any] = {
            "server_info": {},
            "security": {},
            "caching": {},
            "content": {},
            "performance": {},
            "issues": [],
        }
        if "server" in lower_headers:
            analysis["server_info"]["server"] = lower_headers["server"]
        if "x-powered-by" in lower_headers:
            analysis["server_info"]["powered_by"] = lower_headers["x-powered-by"]
        security_headers = [
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "content-security-policy",
        ]
        for header in security_headers:
            if header in lower_headers:
                analysis["security"][header] = lower_headers[header]
            else:
                analysis["issues"].append(f"Missing security header: {header}")
        cache_headers = ["cache-control", "expires", "etag", "last-modified"]
        for header in cache_headers:
            if header in lower_headers:
                analysis["caching"][header] = lower_headers[header]
        if "content-type" in lower_headers:
            analysis["content"]["type"] = lower_headers["content-type"]
        if "content-length" in lower_headers:
            analysis["content"]["length"] = lower_headers["content-length"]
        if "content-encoding" in lower_headers:
            analysis["content"]["encoding"] = lower_headers["content-encoding"]
        if "x-response-time" in lower_headers:
            analysis["performance"]["response_time"] = lower_headers["x-response-time"]
        return analysis
