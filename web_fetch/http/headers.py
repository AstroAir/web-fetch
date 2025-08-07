"""
Enhanced header management for web_fetch.

This module provides comprehensive header management with presets,
validation, and intelligent header handling.
"""

import re
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


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

    def __init__(self) -> None:
        """Initialize header manager."""
        self._rules: List[HeaderRule] = []
        self._global_headers: Dict[str, str] = {}
        self._sensitive_headers: Set[str] = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "proxy-authorization",
            "www-authenticate",
        }

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
        issues: List[str] = []
        for name, value in headers.items():
            # Check header name format
            if not re.match(r"^[a-zA-Z0-9\-_]+$", name):
                issues.append(f"Invalid header name format: {name}")

            # Check for sensitive headers in logs
            if name.lower() in self._sensitive_headers:
                issues.append(f"Sensitive header detected: {name}")

            # Normalize to string for further checks
            is_str = isinstance(value, str)
            str_value = str(value)
            if not is_str:
                issues.append(f"Header value must be string: {name}")

            # Check for control characters
            if re.search(r"[\x00-\x1f\x7f]", str_value):
                issues.append(f"Header value contains control characters: {name}")

        return issues

    def sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for name, value in headers.items():
            if not re.match(r"^[a-zA-Z0-9\-_]+$", name):
                continue
            str_value = str(value)
            clean_value = re.sub(r"[\x00-\x1f\x7f]", "", str_value)
            sanitized[name] = clean_value
        return sanitized

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
