"""
Enhanced header management for web_fetch.

This module provides comprehensive header management with presets,
validation, and intelligent header handling.
"""

import re
from typing import Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class HeaderPresets:
    """Common header presets for different scenarios."""
    
    # Browser-like headers
    BROWSER_CHROME = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    BROWSER_FIREFOX = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # API headers
    API_JSON = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'WebFetch/1.0',
    }
    
    API_XML = {
        'Content-Type': 'application/xml',
        'Accept': 'application/xml',
        'User-Agent': 'WebFetch/1.0',
    }
    
    # Mobile headers
    MOBILE_ANDROID = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    }
    
    MOBILE_IOS = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    }
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
    }


class HeaderRule(BaseModel):
    """Rule for header management."""
    
    pattern: str = Field(description="URL pattern (regex)")
    headers: Dict[str, str] = Field(description="Headers to apply")
    action: str = Field(default="add", description="Action: add, replace, remove")
    priority: int = Field(default=0, description="Rule priority")


class HeaderManager:
    """Advanced header management with rules and validation."""
    
    def __init__(self):
        """Initialize header manager."""
        self._rules: List[HeaderRule] = []
        self._global_headers: Dict[str, str] = {}
        self._sensitive_headers: Set[str] = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token',
            'proxy-authorization', 'www-authenticate'
        }
    
    def add_global_headers(self, headers: Dict[str, str]) -> None:
        """
        Add global headers that apply to all requests.
        
        Args:
            headers: Headers to add globally
        """
        self._global_headers.update(headers)
    
    def remove_global_header(self, header_name: str) -> None:
        """
        Remove a global header.
        
        Args:
            header_name: Header name to remove
        """
        self._global_headers.pop(header_name.lower(), None)
    
    def add_rule(self, rule: HeaderRule) -> None:
        """
        Add a header rule.
        
        Args:
            rule: Header rule to add
        """
        self._rules.append(rule)
        # Sort by priority (higher priority first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, pattern: str) -> None:
        """
        Remove header rules matching pattern.
        
        Args:
            pattern: URL pattern to match
        """
        self._rules = [rule for rule in self._rules if rule.pattern != pattern]
    
    def apply_headers(
        self,
        url: str,
        base_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Apply header rules to generate final headers.
        
        Args:
            url: Request URL
            base_headers: Base headers to start with
            
        Returns:
            Final headers dictionary
        """
        # Start with global headers
        headers = self._global_headers.copy()
        
        # Add base headers
        if base_headers:
            headers.update(base_headers)
        
        # Apply rules in priority order
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
    
    def validate_headers(self, headers: Dict[str, str]) -> List[str]:
        """
        Validate headers and return list of issues.
        
        Args:
            headers: Headers to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        for name, value in headers.items():
            # Check header name format
            if not re.match(r'^[a-zA-Z0-9\-_]+$', name):
                issues.append(f"Invalid header name format: {name}")
            
            # Check for sensitive headers in logs
            if name.lower() in self._sensitive_headers:
                issues.append(f"Sensitive header detected: {name}")
            
            # Check header value
            if not isinstance(value, str):
                issues.append(f"Header value must be string: {name}")
            
            # Check for control characters
            if re.search(r'[\x00-\x1f\x7f]', value):
                issues.append(f"Header value contains control characters: {name}")
        
        return issues
    
    def sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize headers by removing invalid ones.
        
        Args:
            headers: Headers to sanitize
            
        Returns:
            Sanitized headers
        """
        sanitized = {}
        
        for name, value in headers.items():
            # Skip invalid header names
            if not re.match(r'^[a-zA-Z0-9\-_]+$', name):
                continue
            
            # Convert value to string and remove control characters
            str_value = str(value)
            clean_value = re.sub(r'[\x00-\x1f\x7f]', '', str_value)
            
            sanitized[name] = clean_value
        
        return sanitized
    
    def get_headers_for_domain(self, domain: str) -> Dict[str, str]:
        """
        Get headers specific to a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Domain-specific headers
        """
        headers = {}
        
        # Apply domain-specific rules
        for rule in self._rules:
            if domain in rule.pattern or re.match(rule.pattern, f"https://{domain}"):
                if rule.action == "add":
                    headers.update(rule.headers)
        
        return headers
    
    def merge_headers(
        self,
        *header_dicts: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Merge multiple header dictionaries.
        
        Args:
            *header_dicts: Header dictionaries to merge
            
        Returns:
            Merged headers
        """
        merged = {}
        
        for headers in header_dicts:
            if headers:
                merged.update(headers)
        
        return merged
    
    def get_preset_headers(self, preset_name: str) -> Dict[str, str]:
        """
        Get predefined header preset.
        
        Args:
            preset_name: Name of the preset
            
        Returns:
            Preset headers
            
        Raises:
            ValueError: If preset not found
        """
        presets = {
            'browser_chrome': HeaderPresets.BROWSER_CHROME,
            'browser_firefox': HeaderPresets.BROWSER_FIREFOX,
            'api_json': HeaderPresets.API_JSON,
            'api_xml': HeaderPresets.API_XML,
            'mobile_android': HeaderPresets.MOBILE_ANDROID,
            'mobile_ios': HeaderPresets.MOBILE_IOS,
            'security': HeaderPresets.SECURITY_HEADERS,
        }
        
        if preset_name not in presets:
            raise ValueError(f"Unknown header preset: {preset_name}")
        
        return presets[preset_name].copy()
    
    def analyze_response_headers(self, headers: Dict[str, str]) -> Dict[str, any]:
        """
        Analyze response headers for insights.
        
        Args:
            headers: Response headers
            
        Returns:
            Analysis results
        """
        analysis = {
            'server_info': {},
            'security': {},
            'caching': {},
            'content': {},
            'performance': {},
            'issues': []
        }
        
        # Server information
        if 'server' in headers:
            analysis['server_info']['server'] = headers['server']
        
        if 'x-powered-by' in headers:
            analysis['server_info']['powered_by'] = headers['x-powered-by']
        
        # Security analysis
        security_headers = [
            'strict-transport-security', 'x-content-type-options',
            'x-frame-options', 'x-xss-protection', 'content-security-policy'
        ]
        
        for header in security_headers:
            if header in headers:
                analysis['security'][header] = headers[header]
            else:
                analysis['issues'].append(f"Missing security header: {header}")
        
        # Caching analysis
        cache_headers = ['cache-control', 'expires', 'etag', 'last-modified']
        for header in cache_headers:
            if header in headers:
                analysis['caching'][header] = headers[header]
        
        # Content analysis
        if 'content-type' in headers:
            analysis['content']['type'] = headers['content-type']
        
        if 'content-length' in headers:
            analysis['content']['length'] = headers['content-length']
        
        if 'content-encoding' in headers:
            analysis['content']['encoding'] = headers['content-encoding']
        
        # Performance analysis
        if 'x-response-time' in headers:
            analysis['performance']['response_time'] = headers['x-response-time']
        
        return analysis
