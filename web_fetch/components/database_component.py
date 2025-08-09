"""
Database resource component.

This component handles database connections and queries for PostgreSQL,
MySQL, and MongoDB with proper connection pooling and result formatting.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union

from ..models.extended_resources import DatabaseConfig, DatabaseQuery, DatabaseType
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry

logger = logging.getLogger(__name__)

# Optional database driver imports
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import aiomysql
    HAS_AIOMYSQL = True
except ImportError:
    HAS_AIOMYSQL = False

try:
    import motor.motor_asyncio
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False


class DatabaseComponent(ResourceComponent):
    """Resource component for database connections and queries."""
    
    kind = ResourceKind.DATABASE
    
    def __init__(
        self, 
        config: Optional[ResourceConfig] = None,
        db_config: Optional[DatabaseConfig] = None
    ):
        super().__init__(config)
        self.db_config = db_config or DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password="password"
        )
        self._connection_pool = None
        self._mongo_client = None
    
    async def _get_postgresql_pool(self):
        """Get or create PostgreSQL connection pool."""
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for PostgreSQL connections")
        
        if self._connection_pool is None:
            dsn = f"postgresql://{self.db_config.username}:{self.db_config.password.get_secret_value()}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}"
            
            self._connection_pool = await asyncpg.create_pool(
                dsn,
                min_size=self.db_config.min_connections,
                max_size=self.db_config.max_connections,
                command_timeout=self.db_config.query_timeout,
                **self.db_config.extra_params
            )
        
        return self._connection_pool
    
    async def _get_mysql_pool(self):
        """Get or create MySQL connection pool."""
        if not HAS_AIOMYSQL:
            raise ImportError("aiomysql is required for MySQL connections")
        
        if self._connection_pool is None:
            self._connection_pool = await aiomysql.create_pool(
                host=self.db_config.host,
                port=self.db_config.port,
                user=self.db_config.username,
                password=self.db_config.password.get_secret_value(),
                db=self.db_config.database,
                minsize=self.db_config.min_connections,
                maxsize=self.db_config.max_connections,
                **self.db_config.extra_params
            )
        
        return self._connection_pool
    
    async def _get_mongo_client(self):
        """Get or create MongoDB client."""
        if not HAS_MOTOR:
            raise ImportError("motor is required for MongoDB connections")
        
        if self._mongo_client is None:
            connection_string = f"mongodb://{self.db_config.username}:{self.db_config.password.get_secret_value()}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}"
            
            self._mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
                connection_string,
                maxPoolSize=self.db_config.max_connections,
                minPoolSize=self.db_config.min_connections,
                serverSelectionTimeoutMS=int(self.db_config.connection_timeout * 1000),
                **self.db_config.extra_params
            )
        
        return self._mongo_client
    
    async def _execute_postgresql_query(self, query_config: DatabaseQuery) -> Dict[str, Any]:
        """Execute PostgreSQL query."""
        pool = await self._get_postgresql_pool()

        connection = await pool.acquire()
        try:
            if query_config.fetch_mode == "one":
                result = await connection.fetchrow(query_config.query, **(query_config.parameters or {}))
                return {"data": dict(result) if result else None, "row_count": 1 if result else 0}
            elif query_config.fetch_mode == "many":
                limit = query_config.limit or 100
                result = await connection.fetch(query_config.query, **(query_config.parameters or {}))
                limited_result = result[:limit] if result else []
                return {
                    "data": [dict(row) for row in limited_result],
                    "row_count": len(limited_result),
                    "total_rows": len(result) if result else 0
                }
            else:  # "all"
                result = await connection.fetch(query_config.query, **(query_config.parameters or {}))
                return {
                    "data": [dict(row) for row in result] if result else [],
                    "row_count": len(result) if result else 0
                }
        finally:
            await pool.release(connection)
    
    async def _execute_mysql_query(self, query_config: DatabaseQuery) -> Dict[str, Any]:
        """Execute MySQL query."""
        pool = await self._get_mysql_pool()

        connection = await pool.acquire()
        try:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query_config.query, query_config.parameters or {})
                
                if query_config.fetch_mode == "one":
                    result = await cursor.fetchone()
                    return {"data": result, "row_count": 1 if result else 0}
                elif query_config.fetch_mode == "many":
                    limit = query_config.limit or 100
                    result = await cursor.fetchmany(limit)
                    return {"data": result, "row_count": len(result)}
                else:  # "all"
                    result = await cursor.fetchall()
                    return {"data": result, "row_count": len(result)}
        finally:
            pool.release(connection)
    
    async def _execute_mongodb_query(self, query_config: DatabaseQuery) -> Dict[str, Any]:
        """Execute MongoDB query."""
        client = await self._get_mongo_client()
        db = client[self.db_config.database]
        
        # Parse MongoDB query (should be JSON)
        try:
            query_dict = json.loads(query_config.query) if isinstance(query_config.query, str) else query_config.query
        except json.JSONDecodeError:
            raise ValueError("MongoDB query must be valid JSON")
        
        collection_name = query_dict.get("collection")
        operation = query_dict.get("operation", "find")
        filter_query = query_dict.get("filter", {})
        
        if not collection_name:
            raise ValueError("MongoDB query must specify 'collection'")
        
        collection = db[collection_name]
        
        if operation == "find":
            cursor = collection.find(filter_query)
            if query_config.limit:
                cursor = cursor.limit(query_config.limit)
            
            result = await cursor.to_list(length=None)
            return {
                "data": [self._serialize_mongo_doc(doc) for doc in result],
                "row_count": len(result)
            }
        elif operation == "find_one":
            result = await collection.find_one(filter_query)
            return {
                "data": self._serialize_mongo_doc(result) if result else None,
                "row_count": 1 if result else 0
            }
        elif operation == "count":
            count = await collection.count_documents(filter_query)
            return {"data": {"count": count}, "row_count": 1}
        else:
            raise ValueError(f"Unsupported MongoDB operation: {operation}")
    
    def _serialize_mongo_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize MongoDB document for JSON compatibility."""
        if doc is None:
            return None
        
        serialized = {}
        for key, value in doc.items():
            if hasattr(value, '__dict__'):  # ObjectId, etc.
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized
    
    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """
        Execute database query.
        
        Args:
            request: Resource request with database query
            
        Returns:
            ResourceResult with query results
        """
        try:
            # Parse query from request options
            query_data = request.options.get("query")
            if not query_data:
                return ResourceResult(
                    url=str(request.uri),
                    error="Database query not specified in request options"
                )
            
            # Create query configuration
            if isinstance(query_data, dict):
                query_config = DatabaseQuery(**query_data)
            elif isinstance(query_data, str):
                query_config = DatabaseQuery(query=query_data)
            else:
                return ResourceResult(
                    url=str(request.uri),
                    error="Invalid query format"
                )
            
            # Execute query based on database type
            if self.db_config.database_type == DatabaseType.POSTGRESQL:
                result_data = await self._execute_postgresql_query(query_config)
            elif self.db_config.database_type == DatabaseType.MYSQL:
                result_data = await self._execute_mysql_query(query_config)
            elif self.db_config.database_type == DatabaseType.MONGODB:
                result_data = await self._execute_mongodb_query(query_config)
            else:
                return ResourceResult(
                    url=str(request.uri),
                    error=f"Unsupported database type: {self.db_config.database_type}"
                )
            
            # Create result
            result = ResourceResult(
                url=str(request.uri),
                status_code=200,
                content=result_data,
                content_type="application/json"
            )
            
            # Add database metadata
            db_type = self.db_config.database_type.value if hasattr(self.db_config.database_type, 'value') else str(self.db_config.database_type)
            result.metadata = {
                "database": {
                    "type": db_type,
                    "host": self.db_config.host,
                    "database": self.db_config.database,
                    "query_type": query_config.fetch_mode,
                    "row_count": result_data.get("row_count", 0),
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return ResourceResult(
                url=str(request.uri),
                error=f"Database query error: {str(e)}"
            )
    
    async def validate(self, result: ResourceResult) -> ResourceResult:
        """Validate database query result."""
        if result.error:
            return result
        
        try:
            # Add database-specific validation
            if "validation" not in result.metadata:
                result.metadata["validation"] = {}
            
            result.metadata["validation"]["database"] = {
                "has_data": bool(result.content and result.content.get("data")),
                "row_count": result.content.get("row_count", 0) if result.content else 0,
                "is_successful": result.status_code == 200,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Database validation error: {e}")
            result.error = f"Database validation failed: {str(e)}"
            return result
    
    def cache_key(self, request: ResourceRequest) -> Optional[str]:
        """Generate cache key for database query."""
        if not self.config or not self.config.enable_cache:
            return None
        
        query_data = request.options.get("query", {})
        if isinstance(query_data, dict):
            query_str = str(sorted(query_data.items()))
        else:
            query_str = str(query_data)
        
        key_parts = [
            "database",
            self.db_config.database_type.value if hasattr(self.db_config.database_type, 'value') else str(self.db_config.database_type),
            self.db_config.host,
            self.db_config.database,
            query_str,
        ]
        
        return ":".join(key_parts)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        if self._connection_pool:
            if hasattr(self._connection_pool, 'close'):
                self._connection_pool.close()
                if hasattr(self._connection_pool, 'wait_closed'):
                    await self._connection_pool.wait_closed()
        
        if self._mongo_client:
            self._mongo_client.close()


# Register component in the global registry
component_registry.register(ResourceKind.DATABASE, lambda config=None: DatabaseComponent(config))

__all__ = ["DatabaseComponent"]
