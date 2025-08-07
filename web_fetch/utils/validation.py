"""
URL validation and normalization utilities for the web_fetch library.

This module provides comprehensive URL validation, normalization, and analysis
functionality for both HTTP and FTP protocols.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse, urlunparse

from ..models.http import URLAnalysis


class URLValidator:
    """Utility class for URL validation and normalization."""

    # Common URL schemes
    VALID_SCHEMES = {"http", "https", "ftp", "ftps"}

    # Regex patterns for validation
    DOMAIN_PATTERN = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
    )
    IP_PATTERN = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """
        Validate if a URL is properly formatted and uses a supported scheme.

        Args:
            url: URL string to validate

        Returns:
            bool: True if URL is valid, False otherwise
        """
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme.lower() not in cls.VALID_SCHEMES:
                return False

            # Check hostname
            if not parsed.hostname:
                return False

            # Validate hostname format
            hostname = parsed.hostname.lower()
            if not (
                cls.DOMAIN_PATTERN.match(hostname) or cls.IP_PATTERN.match(hostname)
            ):
                return False

            return True

        except Exception:
            return False

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """
        Normalize a URL by standardizing format and removing unnecessary components.

        Args:
            url: URL string to normalize

        Returns:
            str: Normalized URL string
        """
        try:
            parsed = urlparse(url.strip())

            # Normalize scheme to lowercase
            scheme = parsed.scheme.lower()

            # Normalize hostname to lowercase
            hostname = parsed.hostname.lower() if parsed.hostname else ""

            # Handle default ports
            port = parsed.port
            if port:
                if (scheme == "http" and port == 80) or (
                    scheme == "https" and port == 443
                ):
                    port = None
                elif (scheme == "ftp" and port == 21) or (
                    scheme == "ftps" and port == 990
                ):
                    port = None

            # Reconstruct netloc
            netloc = hostname
            if parsed.username:
                auth = parsed.username
                if parsed.password:
                    auth += f":{parsed.password}"
                netloc = f"{auth}@{netloc}"
            if port:
                netloc += f":{port}"

            # Normalize path
            path = parsed.path or "/"
            if not path.startswith("/"):
                path = "/" + path

            # Remove empty query and fragment
            query = parsed.query if parsed.query else ""
            fragment = parsed.fragment if parsed.fragment else ""

            return urlunparse((scheme, netloc, path, parsed.params, query, fragment))

        except Exception:
            return url

    @classmethod
    def analyze_url(cls, url: str) -> URLAnalysis:
        """
        Perform comprehensive analysis of a URL.

        Args:
            url: URL string to analyze

        Returns:
            URLAnalysis: Detailed analysis of the URL
        """
        issues = []
        normalized_url = url

        try:
            parsed = urlparse(url)
            normalized_url = cls.normalize_url(url)

            # Extract components
            scheme = parsed.scheme.lower()
            domain = parsed.hostname.lower() if parsed.hostname else ""
            path = parsed.path or "/"
            query_params = dict(parse_qs(parsed.query)) if parsed.query else {}
            fragment = parsed.fragment or ""
            port = parsed.port

            # Check for issues
            if not scheme:
                issues.append("Missing URL scheme")
            elif scheme not in cls.VALID_SCHEMES:
                issues.append(f"Unsupported scheme: {scheme}")

            if not domain:
                issues.append("Missing domain/hostname")
            elif not (cls.DOMAIN_PATTERN.match(domain) or cls.IP_PATTERN.match(domain)):
                issues.append("Invalid domain format")

            if port and (port < 1 or port > 65535):
                issues.append(f"Invalid port number: {port}")

            # Flatten query params (parse_qs returns lists) to Dict[str, str]
            flat_params: dict[str, str] = {
                k: (v[0] if isinstance(v, list) and v else "")
                for k, v in query_params.items()
            }

            return URLAnalysis(
                original_url=url,
                normalized_url=normalized_url,
                is_valid=len(issues) == 0,
                scheme=scheme,
                domain=domain,
                path=path,
                query_params=flat_params,
                fragment=fragment,
                port=port,
                is_secure=scheme in ("https", "ftps"),
                issues=issues,
            )

        except Exception as e:
            issues.append(f"URL parsing error: {str(e)}")

            return URLAnalysis(
                original_url=url,
                normalized_url=normalized_url,
                is_valid=False,
                scheme="",
                domain="",
                path="",
                query_params={},
                fragment="",
                port=None,
                is_secure=False,
                issues=issues,
            )


def is_valid_url(url: str) -> bool:
    """Convenience function for URL validation."""
    return URLValidator.is_valid_url(url)


def normalize_url(url: str) -> str:
    """Convenience function for URL normalization."""
    return URLValidator.normalize_url(url)


def analyze_url(url: str) -> URLAnalysis:
    """Convenience function for URL analysis."""
    return URLValidator.analyze_url(url)


__all__ = [
    "URLValidator",
    "is_valid_url",
    "normalize_url",
    "analyze_url",
]
