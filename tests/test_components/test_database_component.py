"""
Comprehensive tests for the database component module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, List
import sqlite3
import tempfile
import os

from web_fetch.components.database_component import (
    DatabaseComponent,
    DatabaseConfig,
    DatabaseProvider,
    DatabaseError,
    SQLiteConfig,
    PostgreSQLConfig,
    MySQLConfig,
    MongoDBConfig,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestDatabaseConfig:
    """Test database configuration."""

    def test_sqlite_config_creation(self):
        """Test creating SQLite configuration."""
        config = SQLiteConfig(
            provider=DatabaseProvider.SQLITE,
            database_path="/path/to/database.db",
            table_name="fetch_results"
        )
        
        assert config.provider == DatabaseProvider.SQLITE
        assert config.database_path == "/path/to/database.db"
        assert config.table_name == "fetch_results"

    def test_postgresql_config_creation(self):
        """Test creating PostgreSQL configuration."""
        config = PostgreSQLConfig(
            provider=DatabaseProvider.POSTGRESQL,
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            password="testpass",
            table_name="fetch_results"
        )
        
        assert config.provider == DatabaseProvider.POSTGRESQL
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "testdb"
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_mysql_config_creation(self):
        """Test creating MySQL configuration."""
        config = MySQLConfig(
            provider=DatabaseProvider.MYSQL,
            host="localhost",
            port=3306,
            database="testdb",
            username="testuser",
            password="testpass",
            table_name="fetch_results"
        )
        
        assert config.provider == DatabaseProvider.MYSQL
        assert config.host == "localhost"
        assert config.port == 3306

    def test_mongodb_config_creation(self):
        """Test creating MongoDB configuration."""
        config = MongoDBConfig(
            provider=DatabaseProvider.MONGODB,
            host="localhost",
            port=27017,
            database="testdb",
            collection_name="fetch_results",
            username="testuser",
            password="testpass"
        )
        
        assert config.provider == DatabaseProvider.MONGODB
        assert config.host == "localhost"
        assert config.port == 27017
        assert config.collection_name == "fetch_results"

    def test_database_config_validation(self):
        """Test database configuration validation."""
        # Missing database path for SQLite
        with pytest.raises(ValueError):
            SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path="",
                table_name="results"
            )
        
        # Missing host for PostgreSQL
        with pytest.raises(ValueError):
            PostgreSQLConfig(
                provider=DatabaseProvider.POSTGRESQL,
                host="",
                database="testdb",
                username="user",
                password="pass"
            )


class TestDatabaseProvider:
    """Test database provider enumeration."""

    def test_provider_values(self):
        """Test provider enumeration values."""
        assert DatabaseProvider.SQLITE == "sqlite"
        assert DatabaseProvider.POSTGRESQL == "postgresql"
        assert DatabaseProvider.MYSQL == "mysql"
        assert DatabaseProvider.MONGODB == "mongodb"

    def test_provider_capabilities(self):
        """Test provider capabilities."""
        sql_providers = [
            DatabaseProvider.SQLITE,
            DatabaseProvider.POSTGRESQL,
            DatabaseProvider.MYSQL
        ]
        
        nosql_providers = [
            DatabaseProvider.MONGODB
        ]
        
        assert len(sql_providers) == 3
        assert len(nosql_providers) == 1


class TestDatabaseError:
    """Test database error handling."""

    def test_database_error_creation(self):
        """Test creating database error."""
        error = DatabaseError(
            message="Connection failed",
            provider=DatabaseProvider.POSTGRESQL,
            operation="connect",
            details={"host": "localhost", "port": 5432}
        )
        
        assert error.message == "Connection failed"
        assert error.provider == DatabaseProvider.POSTGRESQL
        assert error.operation == "connect"
        assert error.details["host"] == "localhost"

    def test_database_error_string_representation(self):
        """Test database error string representation."""
        error = DatabaseError(
            message="Query failed",
            provider=DatabaseProvider.MYSQL,
            operation="insert"
        )
        
        error_str = str(error)
        assert "Query failed" in error_str
        assert "mysql" in error_str
        assert "insert" in error_str


class TestDatabaseComponent:
    """Test database component functionality."""

    def test_database_component_creation(self):
        """Test creating database component."""
        config = SQLiteConfig(
            provider=DatabaseProvider.SQLITE,
            database_path=":memory:",
            table_name="test_results"
        )
        
        component = DatabaseComponent(config)
        
        assert component.config == config
        assert component.provider == DatabaseProvider.SQLITE

    @pytest.mark.asyncio
    async def test_sqlite_component_initialization(self):
        """Test SQLite component initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            
            await component.initialize()
            
            assert component.status == "active"
            assert os.path.exists(tmp_db.name)
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_postgresql_component_initialization(self):
        """Test PostgreSQL component initialization."""
        config = PostgreSQLConfig(
            provider=DatabaseProvider.POSTGRESQL,
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        component = DatabaseComponent(config)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            await component.initialize()
            
            assert component.status == "active"
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_mysql_component_initialization(self):
        """Test MySQL component initialization."""
        config = MySQLConfig(
            provider=DatabaseProvider.MYSQL,
            host="localhost",
            port=3306,
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        component = DatabaseComponent(config)
        
        with patch('aiomysql.connect') as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            await component.initialize()
            
            assert component.status == "active"
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_mongodb_component_initialization(self):
        """Test MongoDB component initialization."""
        config = MongoDBConfig(
            provider=DatabaseProvider.MONGODB,
            host="localhost",
            port=27017,
            database="testdb",
            collection_name="fetch_results"
        )
        
        component = DatabaseComponent(config)
        
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            mock_motor_client = MagicMock()
            mock_client.return_value = mock_motor_client
            
            await component.initialize()
            
            assert component.status == "active"
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_fetch_result_sqlite(self):
        """Test storing fetch result in SQLite."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            fetch_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={"content-type": "text/html"},
                content="<html>Test</html>",
                content_type=ContentType.HTML
            )
            
            result = await component.store_fetch_result(fetch_result)
            
            assert result["success"] == True
            assert "record_id" in result
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_store_fetch_result_postgresql(self):
        """Test storing fetch result in PostgreSQL."""
        config = PostgreSQLConfig(
            provider=DatabaseProvider.POSTGRESQL,
            host="localhost",
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        component = DatabaseComponent(config)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_connection = AsyncMock()
            mock_cursor = AsyncMock()
            mock_connection.execute.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            await component.initialize()
            
            fetch_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={"content-type": "text/html"},
                content="<html>Test</html>",
                content_type=ContentType.HTML
            )
            
            result = await component.store_fetch_result(fetch_result)
            
            assert result["success"] == True
            mock_connection.execute.assert_called()

    @pytest.mark.asyncio
    async def test_store_fetch_result_mongodb(self):
        """Test storing fetch result in MongoDB."""
        config = MongoDBConfig(
            provider=DatabaseProvider.MONGODB,
            host="localhost",
            database="testdb",
            collection_name="fetch_results"
        )
        
        component = DatabaseComponent(config)
        
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            mock_motor_client = MagicMock()
            mock_db = MagicMock()
            mock_collection = AsyncMock()
            mock_collection.insert_one.return_value = MagicMock(inserted_id="test_id")
            mock_db.__getitem__.return_value = mock_collection
            mock_motor_client.__getitem__.return_value = mock_db
            mock_client.return_value = mock_motor_client
            
            await component.initialize()
            
            fetch_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={"content-type": "text/html"},
                content="<html>Test</html>",
                content_type=ContentType.HTML
            )
            
            result = await component.store_fetch_result(fetch_result)
            
            assert result["success"] == True
            assert result["record_id"] == "test_id"
            mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_fetch_results_sqlite(self):
        """Test retrieving fetch results from SQLite."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Store a result first
            fetch_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={"content-type": "text/html"},
                content="<html>Test</html>",
                content_type=ContentType.HTML
            )
            
            await component.store_fetch_result(fetch_result)
            
            # Retrieve results
            results = await component.retrieve_fetch_results(
                filters={"url": "https://example.com"}
            )
            
            assert len(results) >= 1
            assert results[0]["url"] == "https://example.com"
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_retrieve_fetch_results_with_limit(self):
        """Test retrieving fetch results with limit."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Store multiple results
            for i in range(5):
                fetch_result = FetchResult(
                    url=f"https://example.com/{i}",
                    status_code=200,
                    headers={},
                    content=f"Content {i}",
                    content_type=ContentType.TEXT
                )
                await component.store_fetch_result(fetch_result)
            
            # Retrieve with limit
            results = await component.retrieve_fetch_results(limit=3)
            
            assert len(results) == 3
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_delete_fetch_results(self):
        """Test deleting fetch results."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Store a result
            fetch_result = FetchResult(
                url="https://example.com/delete",
                status_code=200,
                headers={},
                content="To be deleted",
                content_type=ContentType.TEXT
            )
            
            store_result = await component.store_fetch_result(fetch_result)
            record_id = store_result["record_id"]
            
            # Delete the result
            delete_result = await component.delete_fetch_result(record_id)
            
            assert delete_result["success"] == True
            assert delete_result["deleted_count"] >= 1
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_update_fetch_result(self):
        """Test updating fetch result."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Store a result
            fetch_result = FetchResult(
                url="https://example.com/update",
                status_code=200,
                headers={},
                content="Original content",
                content_type=ContentType.TEXT
            )
            
            store_result = await component.store_fetch_result(fetch_result)
            record_id = store_result["record_id"]
            
            # Update the result
            updates = {"content": "Updated content"}
            update_result = await component.update_fetch_result(record_id, updates)
            
            assert update_result["success"] == True
            assert update_result["updated_count"] >= 1
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_count_fetch_results(self):
        """Test counting fetch results."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Store multiple results
            for i in range(3):
                fetch_result = FetchResult(
                    url=f"https://example.com/count/{i}",
                    status_code=200,
                    headers={},
                    content=f"Content {i}",
                    content_type=ContentType.TEXT
                )
                await component.store_fetch_result(fetch_result)
            
            # Count results
            count = await component.count_fetch_results()
            
            assert count >= 3
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in database operations."""
        config = SQLiteConfig(
            provider=DatabaseProvider.SQLITE,
            database_path="/invalid/path/database.db",
            table_name="fetch_results"
        )
        
        component = DatabaseComponent(config)
        
        with pytest.raises(DatabaseError):
            await component.initialize()

    @pytest.mark.asyncio
    async def test_component_metrics(self):
        """Test database component metrics."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            # Perform some operations
            fetch_result = FetchResult(
                url="https://example.com/metrics",
                status_code=200,
                headers={},
                content="Metrics test",
                content_type=ContentType.TEXT
            )
            
            await component.store_fetch_result(fetch_result)
            await component.store_fetch_result(fetch_result)
            
            metrics = component.get_metrics()
            
            assert metrics["operations_performed"] >= 2
            assert metrics["records_stored"] >= 2
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)

    @pytest.mark.asyncio
    async def test_component_health_check(self):
        """Test database component health check."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            config = SQLiteConfig(
                provider=DatabaseProvider.SQLITE,
                database_path=tmp_db.name,
                table_name="fetch_results"
            )
            
            component = DatabaseComponent(config)
            await component.initialize()
            
            health = await component.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "sqlite"
            assert health["connection_active"] == True
            
            await component.shutdown()
            
            # Clean up
            os.unlink(tmp_db.name)
