"""
Schema management for GraphQL operations.

This module provides schema introspection, caching, and validation coordination
for GraphQL clients, enabling efficient schema management and validation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from pydantic import Field

from ..models import GraphQLConfig, GraphQLSchema
from ..validator import GraphQLValidator
from .base import BaseGraphQLManager, GraphQLManagerConfig

logger = logging.getLogger(__name__)


class SchemaManagerConfig(GraphQLManagerConfig):
    """Configuration for GraphQL schema manager."""
    
    # Schema caching settings
    cache_ttl: float = Field(default=3600.0, ge=0, description="Schema cache TTL in seconds")
    auto_introspect: bool = Field(default=True, description="Automatically introspect schema on initialization")
    validate_queries: bool = Field(default=True, description="Enable query validation against schema")
    
    # Introspection settings
    introspection_timeout: float = Field(default=30.0, ge=1.0, description="Schema introspection timeout")
    retry_introspection: bool = Field(default=True, description="Retry failed introspection attempts")
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class GraphQLSchemaManager(BaseGraphQLManager):
    """
    Schema manager for GraphQL operations.
    
    Manages schema introspection, caching, and validation coordination,
    providing efficient schema operations and query validation.
    
    Features:
    - Schema introspection with caching
    - Configurable cache TTL
    - Query validation coordination
    - Automatic schema refresh
    - Error handling and retry logic
    
    Examples:
        Basic usage:
        ```python
        config = SchemaManagerConfig(cache_ttl=1800.0)
        async with GraphQLSchemaManager(config) as schema_manager:
            schema = await schema_manager.get_schema()
            is_valid = await schema_manager.validate_query(query)
        ```
        
        With custom introspection:
        ```python
        schema_manager = GraphQLSchemaManager(config)
        await schema_manager.initialize()
        
        # Force schema refresh
        await schema_manager.refresh_schema()
        ```
    """
    
    def __init__(
        self,
        config: Optional[SchemaManagerConfig] = None,
        graphql_config: Optional[GraphQLConfig] = None,
        session_manager: Optional[Any] = None,  # GraphQLSessionManager
    ):
        """
        Initialize schema manager.
        
        Args:
            config: Schema manager configuration
            graphql_config: GraphQL client configuration
            session_manager: Session manager for HTTP requests
        """
        super().__init__(config or SchemaManagerConfig())
        self.graphql_config = graphql_config
        self.session_manager = session_manager
        
        # Schema state
        self._schema: Optional[GraphQLSchema] = None
        self._schema_cache_time: Optional[float] = None
        self._validator: Optional[GraphQLValidator] = None
        
        # Introspection state
        self._introspection_in_progress = False
        self._introspection_lock = asyncio.Lock()
        
        # Metrics
        self._introspection_count = 0
        self._validation_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
    
    @property
    def schema_config(self) -> SchemaManagerConfig:
        """Get typed schema configuration."""
        return self.config  # type: ignore
    
    async def _initialize_impl(self) -> None:
        """Initialize schema manager."""
        if self.schema_config.auto_introspect and self.graphql_config:
            try:
                await self.introspect_schema()
                self._logger.debug("Schema introspected during initialization")
            except Exception as e:
                self._logger.warning(f"Failed to introspect schema during initialization: {e}")
                # Don't fail initialization if introspection fails
    
    async def _close_impl(self) -> None:
        """Close schema manager and cleanup resources."""
        self._schema = None
        self._schema_cache_time = None
        self._validator = None
        
        self._logger.info(
            f"Schema manager closed. Metrics: introspections={self._introspection_count}, "
            f"validations={self._validation_count}, cache_hits={self._cache_hits}, "
            f"cache_misses={self._cache_misses}"
        )
    
    async def get_schema(self, force_refresh: bool = False) -> Optional[GraphQLSchema]:
        """
        Get GraphQL schema with caching.
        
        Args:
            force_refresh: Force schema refresh even if cached
            
        Returns:
            GraphQL schema or None if not available
        """
        self._ensure_initialized()
        
        # Check cache validity
        if not force_refresh and self._is_schema_cached():
            self._cache_hits += 1
            return self._schema
        
        # Schema not cached or expired, introspect
        self._cache_misses += 1
        return await self.introspect_schema()
    
    async def introspect_schema(self) -> Optional[GraphQLSchema]:
        """
        Introspect GraphQL schema from endpoint.
        
        Returns:
            GraphQL schema or None if introspection fails
        """
        self._ensure_initialized()
        
        if not self.graphql_config or not self.graphql_config.introspection_enabled:
            self._logger.debug("Schema introspection disabled")
            return None
        
        async with self._introspection_lock:
            if self._introspection_in_progress:
                # Wait for ongoing introspection
                while self._introspection_in_progress:
                    await asyncio.sleep(0.1)
                return self._schema
            
            self._introspection_in_progress = True
            
            try:
                schema = await self._perform_introspection()
                if schema:
                    self._schema = schema
                    self._schema_cache_time = time.time()
                    self._introspection_count += 1
                    
                    # Initialize validator with new schema
                    if self.schema_config.validate_queries:
                        self._validator = GraphQLValidator(schema)
                    
                    self._logger.debug("Schema introspection completed successfully")
                
                return schema
                
            except Exception as e:
                self._logger.error(f"Schema introspection failed: {e}")
                if not self.schema_config.retry_introspection:
                    raise
                return None
            
            finally:
                self._introspection_in_progress = False
    
    async def _perform_introspection(self) -> Optional[GraphQLSchema]:
        """
        Perform the actual schema introspection.
        
        Returns:
            GraphQL schema or None if introspection fails
        """
        if not self.session_manager:
            self._logger.warning("No session manager available for introspection")
            return None
        
        # GraphQL introspection query
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType { name }
                mutationType { name }
                subscriptionType { name }
                types {
                    ...FullType
                }
                directives {
                    name
                    description
                    locations
                    args {
                        ...InputValue
                    }
                }
            }
        }
        
        fragment FullType on __Type {
            kind
            name
            description
            fields(includeDeprecated: true) {
                name
                description
                args {
                    ...InputValue
                }
                type {
                    ...TypeRef
                }
                isDeprecated
                deprecationReason
            }
            inputFields {
                ...InputValue
            }
            interfaces {
                ...TypeRef
            }
            enumValues(includeDeprecated: true) {
                name
                description
                isDeprecated
                deprecationReason
            }
            possibleTypes {
                ...TypeRef
            }
        }
        
        fragment InputValue on __InputValue {
            name
            description
            type { ...TypeRef }
            defaultValue
        }
        
        fragment TypeRef on __Type {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                        ofType {
                            kind
                            name
                            ofType {
                                kind
                                name
                                ofType {
                                    kind
                                    name
                                    ofType {
                                        kind
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            # Use session manager to make introspection request
            async with self.session_manager.get_session() as session:
                headers = {"Content-Type": "application/json"}
                headers = await self.session_manager.apply_authentication(headers)
                
                request_data = {"query": introspection_query}
                
                async with session.post(
                    str(self.graphql_config.endpoint),
                    json=request_data,
                    headers=headers,
                    timeout=self.schema_config.introspection_timeout
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Introspection failed with status {response.status}")
                    
                    response_data = await response.json()
                    
                    if "errors" in response_data:
                        raise Exception(f"Introspection errors: {response_data['errors']}")
                    
                    schema_data = response_data.get("data", {}).get("__schema")
                    if not schema_data:
                        raise Exception("No schema data in introspection response")
                    
                    # Parse schema data into GraphQLSchema
                    return self._parse_schema_data(schema_data)
        
        except Exception as e:
            self._logger.error(f"Introspection request failed: {e}")
            raise
    
    def _parse_schema_data(self, schema_data: Dict[str, Any]) -> GraphQLSchema:
        """
        Parse introspection response into GraphQLSchema.
        
        Args:
            schema_data: Schema data from introspection response
            
        Returns:
            Parsed GraphQL schema
        """
        return GraphQLSchema(
            types=schema_data.get("types", []),
            queries=[],  # Will be populated from queryType
            mutations=[],  # Will be populated from mutationType  
            subscriptions=[],  # Will be populated from subscriptionType
            directives=schema_data.get("directives", [])
        )
    
    async def refresh_schema(self) -> Optional[GraphQLSchema]:
        """
        Force refresh of the schema cache.
        
        Returns:
            Refreshed GraphQL schema
        """
        return await self.get_schema(force_refresh=True)
    
    def _is_schema_cached(self) -> bool:
        """
        Check if schema is cached and valid.
        
        Returns:
            True if schema is cached and not expired
        """
        if not self._schema or not self._schema_cache_time:
            return False
        
        age = time.time() - self._schema_cache_time
        return age < self.schema_config.cache_ttl
    
    async def validate_query(self, query: Any) -> bool:
        """
        Validate a GraphQL query against the schema.
        
        Args:
            query: GraphQL query to validate
            
        Returns:
            True if query is valid
        """
        self._ensure_initialized()
        
        if not self.schema_config.validate_queries:
            return True
        
        if not self._validator:
            # Try to get schema and create validator
            schema = await self.get_schema()
            if schema:
                self._validator = GraphQLValidator(schema)
            else:
                self._logger.warning("No schema available for validation")
                return True  # Allow query if no schema
        
        try:
            self._validation_count += 1
            result = await self._validator.validate(query)
            return result.is_valid
        except Exception as e:
            self._logger.error(f"Query validation failed: {e}")
            return False  # Fail safe
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get schema manager metrics.
        
        Returns:
            Dictionary containing schema metrics
        """
        return {
            "introspection_count": self._introspection_count,
            "validation_count": self._validation_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / max(self._cache_hits + self._cache_misses, 1),
            "schema_cached": self._is_schema_cached(),
            "schema_age": time.time() - self._schema_cache_time if self._schema_cache_time else None,
            "validator_available": self._validator is not None,
        }
