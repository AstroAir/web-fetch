"""
Enhanced cookie management for web_fetch.

This module provides comprehensive cookie handling with persistence,
security features, and domain management.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class Cookie(BaseModel):
    """Cookie model with all attributes."""

    name: str = Field(description="Cookie name")
    value: str = Field(description="Cookie value")
    domain: Optional[str] = Field(default=None, description="Cookie domain")
    path: str = Field(default="/", description="Cookie path")
    expires: Optional[datetime] = Field(default=None, description="Expiration time")
    max_age: Optional[int] = Field(default=None, description="Max age in seconds")
    secure: bool = Field(default=False, description="Secure flag")
    http_only: bool = Field(default=False, description="HttpOnly flag")
    same_site: Optional[str] = Field(default=None, description="SameSite attribute")

    # Internal attributes
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation time"
    )
    last_accessed: datetime = Field(
        default_factory=datetime.now, description="Last access time"
    )

    @property
    def is_expired(self) -> bool:
        """Check if cookie is expired."""
        now = datetime.now()

        if self.expires and now > self.expires:
            return True

        if self.max_age and (now - self.created_at).total_seconds() > self.max_age:
            return True

        return False

    @property
    def is_session_cookie(self) -> bool:
        """Check if this is a session cookie."""
        return self.expires is None and self.max_age is None

    def matches_domain(self, domain: str) -> bool:
        """Check if cookie matches domain."""
        if not self.domain:
            return True

        cookie_domain = self.domain.lower()
        request_domain = domain.lower()

        # Exact match
        if cookie_domain == request_domain:
            return True

        # Domain cookie (starts with .)
        if cookie_domain.startswith("."):
            return request_domain.endswith(cookie_domain[1:])

        return False

    def matches_path(self, path: str) -> bool:
        """Check if cookie matches path."""
        if not self.path:
            return True

        return path.startswith(self.path)

    def to_header_value(self) -> str:
        """Convert cookie to header value format."""
        return f"{self.name}={self.value}"


class CookieJar:
    """Cookie jar for managing cookies."""

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        """
        Initialize cookie jar.

        Args:
            file_path: Optional file path for persistence
        """
        self._cookies: Dict[str, Dict[str, Cookie]] = {}  # domain -> {name: cookie}
        self._file_path = Path(file_path) if file_path else None

        # Load cookies from file if specified
        if self._file_path and self._file_path.exists():
            self.load_from_file()

    def add_cookie(self, cookie: Cookie, url: Optional[str] = None) -> None:
        """
        Add a cookie to the jar.

        Args:
            cookie: Cookie to add
            url: URL context for domain inference
        """
        # Infer domain from URL if not set
        if not cookie.domain and url:
            parsed = urlparse(url)
            cookie.domain = parsed.netloc

        domain = cookie.domain or "default"

        if domain not in self._cookies:
            self._cookies[domain] = {}

        self._cookies[domain][cookie.name] = cookie

        # Save to file if configured
        if self._file_path:
            self.save_to_file()

    def get_cookies_for_url(self, url: str) -> List[Cookie]:
        """
        Get cookies that should be sent with a request to the given URL.

        Args:
            url: Request URL

        Returns:
            List of applicable cookies
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"
        is_secure = parsed.scheme == "https"

        applicable_cookies: List[Cookie] = []

        # Check all domains
        for _cookie_domain, cookies in self._cookies.items():
            for cookie in cookies.values():
                # Skip expired cookies
                if cookie.is_expired:
                    continue

                # Check domain match
                if not cookie.matches_domain(domain):
                    continue

                # Check path match
                if not cookie.matches_path(path):
                    continue

                # Check secure flag
                if cookie.secure and not is_secure:
                    continue

                # Update last accessed time
                cookie.last_accessed = datetime.now()
                applicable_cookies.append(cookie)

        return applicable_cookies

    def get_cookie_header(self, url: str) -> Optional[str]:
        """
        Get Cookie header value for URL.

        Args:
            url: Request URL

        Returns:
            Cookie header value or None
        """
        cookies = self.get_cookies_for_url(url)
        if not cookies:
            return None

        cookie_values = [cookie.to_header_value() for cookie in cookies]
        return "; ".join(cookie_values)

    def parse_set_cookie(self, set_cookie_header: str, url: str) -> None:
        """
        Parse Set-Cookie header and add cookies.

        Args:
            set_cookie_header: Set-Cookie header value
            url: URL context
        """
        # Split multiple cookies
        cookie_strings = set_cookie_header.split(",")

        for cookie_string in cookie_strings:
            cookie = self._parse_single_cookie(cookie_string.strip(), url)
            if cookie:
                self.add_cookie(cookie, url)

    def _parse_single_cookie(self, cookie_string: str, url: str) -> Optional[Cookie]:
        """Parse a single cookie string."""
        parts = [part.strip() for part in cookie_string.split(";")]

        if not parts:
            return None

        # Parse name=value
        name_value = parts[0]
        if "=" not in name_value:
            return None

        name, value = name_value.split("=", 1)

        # Create cookie with defaults
        cookie = Cookie(name=name.strip(), value=value.strip())

        # Parse attributes
        for part in parts[1:]:
            if "=" in part:
                attr_name, attr_value = part.split("=", 1)
                attr_name = attr_name.strip().lower()
                attr_value = attr_value.strip()

                if attr_name == "domain":
                    cookie.domain = attr_value
                elif attr_name == "path":
                    cookie.path = attr_value
                elif attr_name == "expires":
                    try:
                        cookie.expires = datetime.strptime(
                            attr_value, "%a, %d %b %Y %H:%M:%S %Z"
                        )
                    except ValueError:
                        pass
                elif attr_name == "max-age":
                    try:
                        cookie.max_age = int(attr_value)
                    except ValueError:
                        pass
                elif attr_name == "samesite":
                    cookie.same_site = attr_value
            else:
                attr_name = part.strip().lower()
                if attr_name == "secure":
                    cookie.secure = True
                elif attr_name == "httponly":
                    cookie.http_only = True

        # Set default domain if not specified
        if not cookie.domain:
            parsed = urlparse(url)
            cookie.domain = parsed.netloc

        return cookie

    def remove_cookie(self, name: str, domain: Optional[str] = None) -> bool:
        """
        Remove a cookie.

        Args:
            name: Cookie name
            domain: Cookie domain (None for all domains)

        Returns:
            True if cookie was removed
        """
        removed = False

        if domain:
            if domain in self._cookies and name in self._cookies[domain]:
                del self._cookies[domain][name]
                removed = True
        else:
            # Remove from all domains
            for domain_cookies in self._cookies.values():
                if name in domain_cookies:
                    del domain_cookies[name]
                    removed = True

        if removed and self._file_path:
            self.save_to_file()

        return removed

    def clear_expired_cookies(self) -> int:
        """
        Remove expired cookies.

        Returns:
            Number of cookies removed
        """
        removed_count = 0

        for domain in list(self._cookies.keys()):
            for name in list(self._cookies[domain].keys()):
                cookie = self._cookies[domain][name]
                if cookie.is_expired:
                    del self._cookies[domain][name]
                    removed_count += 1

            # Remove empty domains
            if not self._cookies[domain]:
                del self._cookies[domain]

        if removed_count > 0 and self._file_path:
            self.save_to_file()

        return removed_count

    def clear_all_cookies(self) -> None:
        """Clear all cookies."""
        self._cookies.clear()

        if self._file_path:
            self.save_to_file()

    def get_all_cookies(self) -> List[Cookie]:
        """
        Get all cookies.

        Returns:
            List of all cookies
        """
        all_cookies: List[Cookie] = []
        for domain_cookies in self._cookies.values():
            all_cookies.extend(domain_cookies.values())
        return all_cookies

    def save_to_file(self) -> None:
        """Save cookies to file."""
        if not self._file_path:
            return

        # Prepare data for serialization
        data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for domain, cookies in self._cookies.items():
            data[domain] = {}
            for name, cookie in cookies.items():
                cookie_data = cookie.model_dump()
                # Convert datetime objects to ISO strings
                if cookie_data.get("expires"):
                    cookie_data["expires"] = cookie_data["expires"].isoformat()
                cookie_data["created_at"] = cookie_data["created_at"].isoformat()
                cookie_data["last_accessed"] = cookie_data["last_accessed"].isoformat()
                data[domain][name] = cookie_data

        # Save to file
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self) -> None:
        """Load cookies from file."""
        if not self._file_path or not self._file_path.exists():
            return

        try:
            with open(self._file_path, "r") as f:
                data = json.load(f)

            self._cookies.clear()

            for domain, cookies in data.items():
                self._cookies[domain] = {}
                for name, cookie_data in cookies.items():
                    # Convert ISO strings back to datetime objects
                    if cookie_data.get("expires"):
                        cookie_data["expires"] = datetime.fromisoformat(
                            cookie_data["expires"]
                        )
                    cookie_data["created_at"] = datetime.fromisoformat(
                        cookie_data["created_at"]
                    )
                    cookie_data["last_accessed"] = datetime.fromisoformat(
                        cookie_data["last_accessed"]
                    )

                    cookie = Cookie(**cookie_data)
                    self._cookies[domain][name] = cookie

        except Exception:
            # If loading fails, start with empty jar
            self._cookies.clear()


class CookieManager:
    """High-level cookie management."""

    def __init__(self, jar: Optional[CookieJar] = None):
        """
        Initialize cookie manager.

        Args:
            jar: Cookie jar to use
        """
        self.jar = jar or CookieJar()

    def process_response_cookies(
        self, response_headers: Dict[str, str], url: str
    ) -> None:
        """
        Process cookies from response headers.

        Args:
            response_headers: Response headers
            url: Request URL
        """
        # Handle Set-Cookie headers
        set_cookie_headers: List[str] = []

        for name, value in response_headers.items():
            if name.lower() == "set-cookie":
                set_cookie_headers.append(value)

        for header in set_cookie_headers:
            self.jar.parse_set_cookie(header, url)

    def get_request_headers(self, url: str) -> Dict[str, str]:
        """
        Get headers to include in request.

        Args:
            url: Request URL

        Returns:
            Headers dictionary
        """
        headers: Dict[str, str] = {}

        cookie_header = self.jar.get_cookie_header(url)
        if cookie_header:
            headers["Cookie"] = cookie_header

        return headers

    def cleanup_expired_cookies(self) -> int:
        """
        Clean up expired cookies.

        Returns:
            Number of cookies removed
        """
        return self.jar.clear_expired_cookies()
