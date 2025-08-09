"""
Configuration models for extended resource types.

This module defines configuration models for new resource types including
RSS feeds, authenticated APIs, database connections, and cloud storage.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr

from .base import BaseConfig


class FeedFormat(str, Enum):
    """Supported feed formats."""
    
    RSS = "rss"
    ATOM = "atom"
    AUTO = "auto"  # Auto-detect format


class RSSConfig(BaseConfig):
    """Configuration for RSS/Atom feed resources."""
    
    format: FeedFormat = Field(default=FeedFormat.AUTO, description="Feed format preference")
    max_items: int = Field(default=50, ge=1, le=1000, description="Maximum items to parse")
    include_content: bool = Field(default=True, description="Include full content in items")
    validate_dates: bool = Field(default=True, description="Validate and parse dates")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    user_agent: Optional[str] = Field(default=None, description="Custom User-Agent header")


class AuthenticatedAPIConfig(BaseConfig):
    """Configuration for authenticated API endpoints."""
    
    auth_method: str = Field(description="Authentication method (oauth2, api_key, jwt, basic, bearer)")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="Authentication configuration")
    retry_on_auth_failure: bool = Field(default=True, description="Retry request on auth failure")
    refresh_token_threshold: int = Field(default=300, ge=0, description="Seconds before expiry to refresh token")
    base_headers: Dict[str, str] = Field(default_factory=dict, description="Base headers for all requests")


class DatabaseType(str, Enum):
    """Supported database types."""
    
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"


class DatabaseConfig(BaseConfig):
    """Configuration for database connections."""
    
    database_type: DatabaseType = Field(description="Type of database")
    host: str = Field(description="Database host")
    port: int = Field(description="Database port")
    database: str = Field(description="Database name")
    username: str = Field(description="Database username")
    password: SecretStr = Field(description="Database password")
    
    # Connection pool settings
    min_connections: int = Field(default=1, ge=1, description="Minimum connections in pool")
    max_connections: int = Field(default=10, ge=1, description="Maximum connections in pool")
    connection_timeout: float = Field(default=30.0, gt=0, description="Connection timeout in seconds")
    query_timeout: float = Field(default=60.0, gt=0, description="Query timeout in seconds")
    
    # Additional connection parameters
    ssl_mode: Optional[str] = Field(default=None, description="SSL mode for connection")
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Additional connection parameters")


class CloudStorageProvider(str, Enum):
    """Supported cloud storage providers."""
    
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"


class CloudStorageConfig(BaseConfig):
    """Configuration for cloud storage services."""
    
    provider: CloudStorageProvider = Field(description="Cloud storage provider")
    bucket_name: str = Field(description="Storage bucket/container name")
    
    # Authentication credentials
    access_key: Optional[SecretStr] = Field(default=None, description="Access key ID")
    secret_key: Optional[SecretStr] = Field(default=None, description="Secret access key")
    token: Optional[SecretStr] = Field(default=None, description="Session token")
    
    # Provider-specific settings
    region: Optional[str] = Field(default=None, description="Storage region")
    endpoint_url: Optional[str] = Field(default=None, description="Custom endpoint URL")
    
    # Operation settings
    multipart_threshold: int = Field(default=8 * 1024 * 1024, ge=1, description="Multipart upload threshold in bytes")
    max_concurrency: int = Field(default=10, ge=1, description="Maximum concurrent operations")
    retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")
    
    # Additional provider-specific parameters
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Additional provider configuration")


# Query models for database operations
class DatabaseQuery(BaseModel):
    """Database query configuration."""
    
    query: str = Field(description="SQL query or MongoDB query")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    fetch_mode: str = Field(default="all", description="Fetch mode: 'all', 'one', 'many'")
    limit: Optional[int] = Field(default=None, ge=1, description="Result limit")


# Cloud storage operation models
class CloudStorageOperation(BaseModel):
    """Cloud storage operation configuration."""
    
    operation: str = Field(description="Operation type: 'get', 'put', 'list', 'delete', 'copy'")
    key: Optional[str] = Field(default=None, description="Object key/path")
    prefix: Optional[str] = Field(default=None, description="Key prefix for list operations")
    local_path: Optional[str] = Field(default=None, description="Local file path for upload/download")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Object metadata")
    content_type: Optional[str] = Field(default=None, description="Content type for uploads")


__all__ = [
    "FeedFormat",
    "RSSConfig",
    "AuthenticatedAPIConfig", 
    "DatabaseType",
    "DatabaseConfig",
    "CloudStorageProvider",
    "CloudStorageConfig",
    "DatabaseQuery",
    "CloudStorageOperation",
]
