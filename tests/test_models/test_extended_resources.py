"""
Comprehensive tests for extended resource models in web_fetch.models.extended_resources module.

Tests configuration models for RSS feeds, authenticated APIs, database connections, and cloud storage.
"""

import pytest
from pydantic import ValidationError, SecretStr

from web_fetch.models.extended_resources import (
    FeedFormat,
    RSSConfig,
    AuthenticatedAPIConfig,
    DatabaseType,
    DatabaseConfig,
    CloudStorageProvider,
    CloudStorageConfig,
    DatabaseQuery,
    CloudStorageOperation,
)


class TestFeedFormat:
    """Test FeedFormat enumeration."""

    def test_all_feed_formats(self):
        """Test all feed format values."""
        assert FeedFormat.RSS == "rss"
        assert FeedFormat.ATOM == "atom"
        assert FeedFormat.AUTO == "auto"

    def test_feed_format_string_behavior(self):
        """Test that FeedFormat behaves as string."""
        format_type = FeedFormat.RSS
        assert str(format_type) == "rss"
        assert format_type == "rss"


class TestRSSConfig:
    """Test RSSConfig model."""

    def test_default_config(self):
        """Test default RSS configuration."""
        config = RSSConfig()
        assert config.format == FeedFormat.AUTO
        assert config.max_items == 50
        assert config.include_content is True
        assert config.validate_dates is True
        assert config.follow_redirects is True
        assert config.user_agent is None

    def test_custom_config(self):
        """Test custom RSS configuration."""
        config = RSSConfig(
            format=FeedFormat.RSS,
            max_items=100,
            include_content=False,
            validate_dates=False,
            follow_redirects=False,
            user_agent="Custom RSS Reader 1.0"
        )
        assert config.format == FeedFormat.RSS
        assert config.max_items == 100
        assert config.include_content is False
        assert config.validate_dates is False
        assert config.follow_redirects is False
        assert config.user_agent == "Custom RSS Reader 1.0"

    def test_max_items_validation(self):
        """Test max_items validation."""
        # Valid values
        RSSConfig(max_items=1)
        RSSConfig(max_items=500)
        RSSConfig(max_items=1000)

        # Invalid values
        with pytest.raises(ValidationError):
            RSSConfig(max_items=0)

        with pytest.raises(ValidationError):
            RSSConfig(max_items=1001)

        with pytest.raises(ValidationError):
            RSSConfig(max_items=-1)


class TestAuthenticatedAPIConfig:
    """Test AuthenticatedAPIConfig model."""

    def test_basic_config(self):
        """Test basic authenticated API configuration."""
        config = AuthenticatedAPIConfig(auth_method="oauth2")
        assert config.auth_method == "oauth2"
        assert config.auth_config == {}
        assert config.retry_on_auth_failure is True
        assert config.refresh_token_threshold == 300
        assert config.base_headers == {}

    def test_oauth2_config(self):
        """Test OAuth2 configuration."""
        auth_config = {
            "client_id": "client123",
            "client_secret": "secret456",
            "token_url": "https://auth.example.com/token",
            "scope": "read write"
        }
        base_headers = {"User-Agent": "MyApp/1.0"}

        config = AuthenticatedAPIConfig(
            auth_method="oauth2",
            auth_config=auth_config,
            retry_on_auth_failure=False,
            refresh_token_threshold=600,
            base_headers=base_headers
        )

        assert config.auth_method == "oauth2"
        assert config.auth_config == auth_config
        assert config.retry_on_auth_failure is False
        assert config.refresh_token_threshold == 600
        assert config.base_headers == base_headers

    def test_api_key_config(self):
        """Test API key configuration."""
        auth_config = {
            "api_key": "key123",
            "header_name": "X-API-Key"
        }

        config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config=auth_config
        )

        assert config.auth_method == "api_key"
        assert config.auth_config == auth_config

    def test_jwt_config(self):
        """Test JWT configuration."""
        auth_config = {
            "secret": "jwt_secret",
            "algorithm": "HS256",
            "payload": {"user_id": 123}
        }

        config = AuthenticatedAPIConfig(
            auth_method="jwt",
            auth_config=auth_config
        )

        assert config.auth_method == "jwt"
        assert config.auth_config == auth_config

    def test_refresh_token_threshold_validation(self):
        """Test refresh token threshold validation."""
        # Valid values
        AuthenticatedAPIConfig(auth_method="oauth2", refresh_token_threshold=0)
        AuthenticatedAPIConfig(auth_method="oauth2", refresh_token_threshold=3600)

        # Invalid values
        with pytest.raises(ValidationError):
            AuthenticatedAPIConfig(auth_method="oauth2", refresh_token_threshold=-1)


class TestDatabaseType:
    """Test DatabaseType enumeration."""

    def test_all_database_types(self):
        """Test all database type values."""
        assert DatabaseType.POSTGRESQL == "postgresql"
        assert DatabaseType.MYSQL == "mysql"
        assert DatabaseType.MONGODB == "mongodb"
        assert DatabaseType.SQLITE == "sqlite"

    def test_database_type_string_behavior(self):
        """Test that DatabaseType behaves as string."""
        db_type = DatabaseType.POSTGRESQL
        assert str(db_type) == "postgresql"
        assert db_type == "postgresql"


class TestDatabaseConfig:
    """Test DatabaseConfig model."""

    def test_postgresql_config(self):
        """Test PostgreSQL configuration."""
        config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password=SecretStr("password123")
        )

        assert config.database_type == DatabaseType.POSTGRESQL
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "mydb"
        assert config.username == "user"
        assert config.password.get_secret_value() == "password123"

        # Default values
        assert config.min_connections == 1
        assert config.max_connections == 10
        assert config.connection_timeout == 30.0
        assert config.query_timeout == 60.0
        assert config.ssl_mode is None
        assert config.extra_params == {}

    def test_mysql_config(self):
        """Test MySQL configuration."""
        config = DatabaseConfig(
            database_type=DatabaseType.MYSQL,
            host="mysql.example.com",
            port=3306,
            database="app_db",
            username="app_user",
            password=SecretStr("mysql_pass"),
            min_connections=2,
            max_connections=20,
            connection_timeout=15.0,
            query_timeout=30.0,
            ssl_mode="required",
            extra_params={"charset": "utf8mb4"}
        )

        assert config.database_type == DatabaseType.MYSQL
        assert config.host == "mysql.example.com"
        assert config.port == 3306
        assert config.min_connections == 2
        assert config.max_connections == 20
        assert config.connection_timeout == 15.0
        assert config.query_timeout == 30.0
        assert config.ssl_mode == "required"
        assert config.extra_params == {"charset": "utf8mb4"}

    def test_mongodb_config(self):
        """Test MongoDB configuration."""
        config = DatabaseConfig(
            database_type=DatabaseType.MONGODB,
            host="mongo.example.com",
            port=27017,
            database="app_db",
            username="mongo_user",
            password=SecretStr("mongo_pass"),
            extra_params={
                "authSource": "admin",
                "replicaSet": "rs0"
            }
        )

        assert config.database_type == DatabaseType.MONGODB
        assert config.port == 27017
        assert config.extra_params["authSource"] == "admin"
        assert config.extra_params["replicaSet"] == "rs0"

    def test_sqlite_config(self):
        """Test SQLite configuration."""
        config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            host="",  # Not used for SQLite
            port=0,   # Not used for SQLite
            database="/path/to/database.db",
            username="",  # Not used for SQLite
            password=SecretStr("")  # Not used for SQLite
        )

        assert config.database_type == DatabaseType.SQLITE
        assert config.database == "/path/to/database.db"

    def test_connection_validation(self):
        """Test connection pool validation."""
        # Valid values
        DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="db",
            username="user",
            password=SecretStr("pass"),
            min_connections=1,
            max_connections=1
        )

        # Invalid min_connections
        with pytest.raises(ValidationError):
            DatabaseConfig(
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database="db",
                username="user",
                password=SecretStr("pass"),
                min_connections=0
            )

        # Invalid max_connections
        with pytest.raises(ValidationError):
            DatabaseConfig(
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database="db",
                username="user",
                password=SecretStr("pass"),
                max_connections=0
            )

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="db",
            username="user",
            password=SecretStr("pass"),
            connection_timeout=0.1,
            query_timeout=0.1
        )

        # Invalid connection_timeout
        with pytest.raises(ValidationError):
            DatabaseConfig(
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database="db",
                username="user",
                password=SecretStr("pass"),
                connection_timeout=0.0
            )

        # Invalid query_timeout
        with pytest.raises(ValidationError):
            DatabaseConfig(
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database="db",
                username="user",
                password=SecretStr("pass"),
                query_timeout=-1.0
            )


class TestCloudStorageProvider:
    """Test CloudStorageProvider enumeration."""

    def test_all_providers(self):
        """Test all cloud storage provider values."""
        assert CloudStorageProvider.AWS_S3 == "aws_s3"
        assert CloudStorageProvider.GOOGLE_CLOUD == "google_cloud"
        assert CloudStorageProvider.AZURE_BLOB == "azure_blob"

    def test_provider_string_behavior(self):
        """Test that CloudStorageProvider behaves as string."""
        provider = CloudStorageProvider.AWS_S3
        assert str(provider) == "aws_s3"
        assert provider == "aws_s3"


class TestCloudStorageConfig:
    """Test CloudStorageConfig model."""

    def test_aws_s3_config(self):
        """Test AWS S3 configuration."""
        config = CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="my-s3-bucket",
            access_key=SecretStr("AKIAIOSFODNN7EXAMPLE"),
            secret_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
            region="us-west-2"
        )

        assert config.provider == CloudStorageProvider.AWS_S3
        assert config.bucket_name == "my-s3-bucket"
        assert config.access_key.get_secret_value() == "AKIAIOSFODNN7EXAMPLE"
        assert config.secret_key.get_secret_value() == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert config.region == "us-west-2"

        # Default values
        assert config.token is None
        assert config.endpoint_url is None
        assert config.multipart_threshold == 8 * 1024 * 1024
        assert config.max_concurrency == 10
        assert config.retry_attempts == 3
        assert config.extra_config == {}

    def test_google_cloud_config(self):
        """Test Google Cloud Storage configuration."""
        config = CloudStorageConfig(
            provider=CloudStorageProvider.GOOGLE_CLOUD,
            bucket_name="my-gcs-bucket",
            access_key=SecretStr("gcs_access_key"),
            secret_key=SecretStr("gcs_secret_key"),
            extra_config={
                "project_id": "my-project",
                "credentials_path": "/path/to/credentials.json"
            }
        )

        assert config.provider == CloudStorageProvider.GOOGLE_CLOUD
        assert config.bucket_name == "my-gcs-bucket"
        assert config.extra_config["project_id"] == "my-project"
        assert config.extra_config["credentials_path"] == "/path/to/credentials.json"

    def test_azure_blob_config(self):
        """Test Azure Blob Storage configuration."""
        config = CloudStorageConfig(
            provider=CloudStorageProvider.AZURE_BLOB,
            bucket_name="my-container",
            access_key=SecretStr("azure_account_name"),
            secret_key=SecretStr("azure_account_key"),
            extra_config={
                "account_url": "https://myaccount.blob.core.windows.net"
            }
        )

        assert config.provider == CloudStorageProvider.AZURE_BLOB
        assert config.bucket_name == "my-container"
        assert config.extra_config["account_url"] == "https://myaccount.blob.core.windows.net"

    def test_custom_settings(self):
        """Test custom storage settings."""
        config = CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            multipart_threshold=16 * 1024 * 1024,  # 16MB
            max_concurrency=20,
            retry_attempts=5,
            endpoint_url="https://s3.custom-endpoint.com",
            token=SecretStr("session_token_123")
        )

        assert config.multipart_threshold == 16 * 1024 * 1024
        assert config.max_concurrency == 20
        assert config.retry_attempts == 5
        assert config.endpoint_url == "https://s3.custom-endpoint.com"
        assert config.token.get_secret_value() == "session_token_123"

    def test_validation(self):
        """Test configuration validation."""
        # Valid values
        CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="valid-bucket",
            multipart_threshold=1,
            max_concurrency=1,
            retry_attempts=0
        )

        # Invalid multipart_threshold
        with pytest.raises(ValidationError):
            CloudStorageConfig(
                provider=CloudStorageProvider.AWS_S3,
                bucket_name="test-bucket",
                multipart_threshold=0
            )

        # Invalid max_concurrency
        with pytest.raises(ValidationError):
            CloudStorageConfig(
                provider=CloudStorageProvider.AWS_S3,
                bucket_name="test-bucket",
                max_concurrency=0
            )

        # Invalid retry_attempts
        with pytest.raises(ValidationError):
            CloudStorageConfig(
                provider=CloudStorageProvider.AWS_S3,
                bucket_name="test-bucket",
                retry_attempts=-1
            )


class TestDatabaseQuery:
    """Test DatabaseQuery model."""

    def test_basic_query(self):
        """Test basic database query."""
        query = DatabaseQuery(query="SELECT * FROM users")
        assert query.query == "SELECT * FROM users"
        assert query.parameters is None
        assert query.fetch_mode == "all"
        assert query.limit is None

    def test_parameterized_query(self):
        """Test parameterized query."""
        query = DatabaseQuery(
            query="SELECT * FROM users WHERE age > ? AND city = ?",
            parameters={"age": 18, "city": "New York"},
            fetch_mode="many",
            limit=100
        )

        assert query.query == "SELECT * FROM users WHERE age > ? AND city = ?"
        assert query.parameters == {"age": 18, "city": "New York"}
        assert query.fetch_mode == "many"
        assert query.limit == 100

    def test_mongodb_query(self):
        """Test MongoDB-style query."""
        query = DatabaseQuery(
            query='{"age": {"$gt": 18}, "status": "active"}',
            parameters=None,
            fetch_mode="all"
        )

        assert '{"age": {"$gt": 18}' in query.query
        assert query.parameters is None

    def test_limit_validation(self):
        """Test limit validation."""
        # Valid limit
        DatabaseQuery(query="SELECT * FROM users", limit=1)
        DatabaseQuery(query="SELECT * FROM users", limit=1000)

        # Invalid limit
        with pytest.raises(ValidationError):
            DatabaseQuery(query="SELECT * FROM users", limit=0)

        with pytest.raises(ValidationError):
            DatabaseQuery(query="SELECT * FROM users", limit=-1)


class TestCloudStorageOperation:
    """Test CloudStorageOperation model."""

    def test_get_operation(self):
        """Test get operation."""
        operation = CloudStorageOperation(
            operation="get",
            key="path/to/file.txt",
            local_path="/tmp/downloaded_file.txt"
        )

        assert operation.operation == "get"
        assert operation.key == "path/to/file.txt"
        assert operation.local_path == "/tmp/downloaded_file.txt"
        assert operation.prefix is None
        assert operation.metadata == {}
        assert operation.content_type is None

    def test_put_operation(self):
        """Test put operation."""
        metadata = {"author": "user123", "version": "1.0"}

        operation = CloudStorageOperation(
            operation="put",
            key="uploads/document.pdf",
            local_path="/home/user/document.pdf",
            metadata=metadata,
            content_type="application/pdf"
        )

        assert operation.operation == "put"
        assert operation.key == "uploads/document.pdf"
        assert operation.local_path == "/home/user/document.pdf"
        assert operation.metadata == metadata
        assert operation.content_type == "application/pdf"

    def test_list_operation(self):
        """Test list operation."""
        operation = CloudStorageOperation(
            operation="list",
            prefix="images/"
        )

        assert operation.operation == "list"
        assert operation.prefix == "images/"
        assert operation.key is None
        assert operation.local_path is None

    def test_delete_operation(self):
        """Test delete operation."""
        operation = CloudStorageOperation(
            operation="delete",
            key="old/file.txt"
        )

        assert operation.operation == "delete"
        assert operation.key == "old/file.txt"

    def test_copy_operation(self):
        """Test copy operation."""
        operation = CloudStorageOperation(
            operation="copy",
            key="source/file.txt",
            metadata={"destination": "backup/file.txt"}
        )

        assert operation.operation == "copy"
        assert operation.key == "source/file.txt"
        assert operation.metadata["destination"] == "backup/file.txt"
