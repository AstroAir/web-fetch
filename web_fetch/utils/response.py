"""
Response analysis utility module for the web_fetch library.

This module provides functionality for analyzing HTTP responses and headers.
"""

from __future__ import annotations

import json
from typing import Dict

from ..models import HeaderAnalysis


class ResponseAnalyzer:
    """Utility class for analyzing HTTP responses."""
    
    SECURITY_HEADERS = {
        'strict-transport-security',
        'content-security-policy',
        'x-frame-options',
        'x-content-type-options',
        'x-xss-protection',
        'referrer-policy'
    }
    
    @classmethod
    def analyze_headers(cls, headers: Dict[str, str]) -> HeaderAnalysis:
        """
        Analyze HTTP response headers.
        
        Args:
            headers: Dictionary of response headers
            
        Returns:
            HeaderAnalysis object with parsed header information
        """
        # Normalize header names to lowercase
        normalized_headers = {k.lower(): v for k, v in headers.items()}
        
        # Extract common headers
        content_type = normalized_headers.get('content-type')
        content_length = None
        if 'content-length' in normalized_headers:
            try:
                content_length = int(normalized_headers['content-length'])
            except ValueError:
                pass
        
        content_encoding = normalized_headers.get('content-encoding')
        server = normalized_headers.get('server')
        cache_control = normalized_headers.get('cache-control')
        etag = normalized_headers.get('etag')
        last_modified = normalized_headers.get('last-modified')
        expires = normalized_headers.get('expires')
        
        # Extract security headers
        security_headers = {
            k: v for k, v in normalized_headers.items()
            if k in cls.SECURITY_HEADERS
        }
        
        # Extract custom headers (non-standard)
        standard_headers = {
            'content-type', 'content-length', 'content-encoding', 'server',
            'cache-control', 'etag', 'last-modified', 'expires', 'date',
            'connection', 'transfer-encoding', 'location', 'set-cookie'
        }
        custom_headers = {
            k: v for k, v in normalized_headers.items()
            if k not in standard_headers and k not in cls.SECURITY_HEADERS
        }
        
        return HeaderAnalysis(
            content_type=content_type,
            content_length=content_length,
            content_encoding=content_encoding,
            server=server,
            cache_control=cache_control,
            etag=etag,
            last_modified=last_modified,
            expires=expires,
            security_headers=security_headers,
            custom_headers=custom_headers
        )
    
    @classmethod
    def detect_content_type(cls, headers: Dict[str, str], content: bytes) -> str:
        """
        Detect content type from headers and content.
        
        Args:
            headers: Response headers
            content: Response content bytes
            
        Returns:
            Detected content type string
        """
        # Check Content-Type header first
        content_type = headers.get('content-type', '').lower()
        if content_type:
            return content_type.split(';')[0].strip()
        
        # Try to detect from content
        if not content:
            return 'application/octet-stream'
        
        # Check for common file signatures
        if content.startswith(b'<!DOCTYPE html') or content.startswith(b'<html'):
            return 'text/html'
        elif content.startswith(b'{') or content.startswith(b'['):
            try:
                json.loads(content.decode('utf-8'))
                return 'application/json'
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        elif content.startswith(b'<?xml'):
            return 'application/xml'
        elif content.startswith(b'\x89PNG'):
            return 'image/png'
        elif content.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif content.startswith(b'GIF8'):
            return 'image/gif'
        elif content.startswith(b'%PDF'):
            return 'application/pdf'
        
        # Try to decode as text
        try:
            content.decode('utf-8')
            return 'text/plain'
        except UnicodeDecodeError:
            return 'application/octet-stream'
