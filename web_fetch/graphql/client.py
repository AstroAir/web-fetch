"""
GraphQL client implementation.

This module provides a comprehensive GraphQL client with schema introspection,
query validation, and advanced GraphQL features.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp

from .models import (
    GraphQLConfig,
    GraphQLQuery,
    GraphQLMutation,
    GraphQLSubscription,
    GraphQLResult,
    GraphQLError,
    GraphQLSchema,
)
from .validator import GraphQLValidator
from ..auth import AuthManager
from ..exceptions import WebFetchError

logger = logging.getLogger(__name__)


class GraphQLClient:
    """
    Comprehensive GraphQL client with advanced features.
    
    The GraphQLClient provides a full-featured GraphQL implementation with:
    - Schema introspection and caching
    - Query validation and optimization
    - Subscription support via WebSocket
    - Query batching for performance
    - Response caching
    - Authentication integration
    - Error handling and retry logic
    
    Examples:
        Basic GraphQL query:
        ```python
        config = GraphQLConfig(
            endpoint="https://api.example.com/graphql",
            validate_queries=True
        )
        
        async with GraphQLClient(config) as client:
            query = GraphQLQuery(
                query='''
                    query GetUser($id: ID!) {
                        user(id: $id) {
                            name
                            email
                            profile {
                                avatar
                            }
                        }
                    }
                ''',
                variables={"id": "123"}
            )
            
            result = await client.execute(query)
            if result.success:
                user = result.get_data("user")
                print(f"User: {user['name']}")
        ```
        
        GraphQL mutation:
        ```python
        mutation = GraphQLMutation(
            query='''
                mutation CreateUser($input: CreateUserInput!) {
                    createUser(input: $input) {
                        id
                        name
                        email
                    }
                }
            ''',
            variables={
                "input": {
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }
        )
        
        result = await client.execute(mutation)
        ```
        
        With authentication:
        ```python
        from web_fetch.auth import AuthManager, BearerTokenAuth, BearerTokenConfig
        
        auth_config = BearerTokenConfig(token="your-jwt-token")
        auth_manager = AuthManager()
        auth_manager.add_auth_method("bearer", BearerTokenAuth(auth_config))
        
        client = GraphQLClient(config, auth_manager=auth_manager)
        ```
    """
    
    def __init__(
        self,
        config: GraphQLConfig,
        auth_manager: Optional[AuthManager] = None
    ):
        """
        Initialize GraphQL client.
        
        Args:
            config: GraphQL configuration
            auth_manager: Optional authentication manager
        """
        self.config = config
        self.auth_manager = auth_manager
        self._session: Optional[aiohttp.ClientSession] = None
        self._schema: Optional[GraphQLSchema] = None
        self._schema_cache_time: Optional[float] = None
        self._validator: Optional[GraphQLValidator] = None
        self._response_cache: Dict[str, Any] = {}
        self._batch_queue: List[GraphQLQuery] = []
        self._batch_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self) -> GraphQLClient:
        """Async context manager entry."""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self._close_session()
    
    async def _create_session(self) -> None:
        """Create HTTP session."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def execute(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        use_cache: bool = True
    ) -> GraphQLResult:
        """
        Execute a GraphQL operation.
        
        Args:
            query: GraphQL query, mutation, or subscription
            use_cache: Whether to use response caching
            
        Returns:
            GraphQLResult with operation result
            
        Raises:
            GraphQLError: If operation fails
        """
        if not self._session:
            await self._create_session()
        
        try:
            # Validate query if enabled
            if self.config.validate_queries:
                await self._validate_query(query)
            
            # Check cache for queries (not mutations/subscriptions)
            if (use_cache and 
                self.config.enable_response_caching and 
                isinstance(query, GraphQLQuery) and 
                not isinstance(query, (GraphQLMutation, GraphQLSubscription))):
                
                cached_result = self._get_cached_response(query)
                if cached_result:
                    return cached_result
            
            # Execute the operation
            start_time = time.time()
            
            # Prepare request
            request_data = query.to_dict()
            headers = self.config.headers.copy()
            headers["Content-Type"] = "application/json"
            
            # Add authentication if available
            if self.auth_manager:
                auth_result = await self.auth_manager.authenticate_for_url(str(self.config.endpoint))
                if auth_result.success:
                    headers.update(auth_result.headers)
            
            # Make request
            async with self._session.post(
                str(self.config.endpoint),
                json=request_data,
                headers=headers
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()
                
                # Parse response
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError:
                    raise GraphQLError(f"Invalid JSON response: {response_text}")
                
                # Create result
                result = GraphQLResult(
                    success=response.status == 200 and "errors" not in response_data,
                    data=response_data.get("data"),
                    errors=response_data.get("errors", []),
                    extensions=response_data.get("extensions") if self.config.include_extensions else None,
                    response_time=response_time,
                    status_code=response.status,
                    headers=dict(response.headers),
                    raw_response=response_text
                )
                
                # Handle errors
                if result.has_errors and self.config.raise_on_errors:
                    error_messages = "; ".join(result.error_messages)
                    raise GraphQLError(f"GraphQL errors: {error_messages}")
                
                # Cache successful query results
                if (result.success and 
                    self.config.enable_response_caching and 
                    isinstance(query, GraphQLQuery) and 
                    not isinstance(query, (GraphQLMutation, GraphQLSubscription))):
                    self._cache_response(query, result)
                
                return result
                
        except aiohttp.ClientError as e:
            raise GraphQLError(f"HTTP error: {str(e)}")
        except Exception as e:
            if isinstance(e, GraphQLError):
                raise
            raise GraphQLError(f"Unexpected error: {str(e)}")
    
    async def execute_batch(self, queries: List[GraphQLQuery]) -> List[GraphQLResult]:
        """
        Execute multiple queries in a batch.
        
        Args:
            queries: List of GraphQL queries
            
        Returns:
            List of GraphQLResult objects
            
        Raises:
            GraphQLError: If batch execution fails
        """
        if not self.config.enable_query_batching:
            # Execute queries individually
            results = []
            for query in queries:
                result = await self.execute(query)
                results.append(result)
            return results
        
        if not self._session:
            await self._create_session()
        
        try:
            # Prepare batch request
            batch_data = [query.to_dict() for query in queries]
            headers = self.config.headers.copy()
            headers["Content-Type"] = "application/json"
            
            # Add authentication
            if self.auth_manager:
                auth_result = await self.auth_manager.authenticate_for_url(str(self.config.endpoint))
                if auth_result.success:
                    headers.update(auth_result.headers)
            
            start_time = time.time()
            
            # Make batch request
            async with self._session.post(
                str(self.config.endpoint),
                json=batch_data,
                headers=headers
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()
                
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError:
                    raise GraphQLError(f"Invalid JSON response: {response_text}")
                
                # Parse batch results
                if not isinstance(response_data, list):
                    raise GraphQLError("Expected array response for batch request")
                
                results = []
                for i, item in enumerate(response_data):
                    result = GraphQLResult(
                        success=response.status == 200 and "errors" not in item,
                        data=item.get("data"),
                        errors=item.get("errors", []),
                        extensions=item.get("extensions") if self.config.include_extensions else None,
                        response_time=response_time / len(response_data),  # Approximate
                        status_code=response.status,
                        headers=dict(response.headers),
                        raw_response=json.dumps(item)
                    )
                    results.append(result)
                
                return results
                
        except aiohttp.ClientError as e:
            raise GraphQLError(f"HTTP error in batch request: {str(e)}")
        except Exception as e:
            if isinstance(e, GraphQLError):
                raise
            raise GraphQLError(f"Unexpected error in batch request: {str(e)}")
    
    async def introspect_schema(self, force_refresh: bool = False) -> GraphQLSchema:
        """
        Introspect GraphQL schema.
        
        Args:
            force_refresh: Force schema refresh even if cached
            
        Returns:
            GraphQLSchema object
            
        Raises:
            GraphQLError: If introspection fails
        """
        # Check cache
        if (not force_refresh and 
            self._schema and 
            self._schema_cache_time and 
            time.time() - self._schema_cache_time < self.config.schema_cache_ttl):
            return self._schema
        
        if not self.config.introspection_enabled:
            raise GraphQLError("Schema introspection is disabled")
        
        # Introspection query
        introspection_query = GraphQLQuery(
            query='''
                query IntrospectionQuery {
                    __schema {
                        types {
                            name
                            kind
                            description
                            fields {
                                name
                                type {
                                    name
                                    kind
                                }
                            }
                        }
                        queryType {
                            name
                            fields {
                                name
                                description
                                type {
                                    name
                                    kind
                                }
                            }
                        }
                        mutationType {
                            name
                            fields {
                                name
                                description
                                type {
                                    name
                                    kind
                                }
                            }
                        }
                        subscriptionType {
                            name
                            fields {
                                name
                                description
                                type {
                                    name
                                    kind
                                }
                            }
                        }
                        directives {
                            name
                            description
                            locations
                        }
                    }
                }
            '''
        )
        
        result = await self.execute(introspection_query, use_cache=False)
        
        if not result.success:
            raise GraphQLError(f"Schema introspection failed: {result.error_messages}")
        
        schema_data = result.get_data("__schema")
        if not schema_data:
            raise GraphQLError("No schema data in introspection response")
        
        # Parse schema
        self._schema = GraphQLSchema(
            types=schema_data.get("types", []),
            queries=schema_data.get("queryType", {}).get("fields", []),
            mutations=schema_data.get("mutationType", {}).get("fields", []) if schema_data.get("mutationType") else [],
            subscriptions=schema_data.get("subscriptionType", {}).get("fields", []) if schema_data.get("subscriptionType") else [],
            directives=schema_data.get("directives", [])
        )
        
        self._schema_cache_time = time.time()
        
        # Initialize validator with schema
        if self.config.validate_queries:
            self._validator = GraphQLValidator(self._schema)
        
        return self._schema
    
    async def _validate_query(self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]) -> None:
        """Validate GraphQL query against schema."""
        if not query.validate():
            raise GraphQLError("Invalid query syntax")
        
        if self._validator:
            validation_result = await self._validator.validate(query)
            if not validation_result.is_valid:
                raise GraphQLError(f"Query validation failed: {validation_result.errors}")
    
    def _get_cached_response(self, query: GraphQLQuery) -> Optional[GraphQLResult]:
        """Get cached response for query."""
        cache_key = self._generate_cache_key(query)
        cached_item = self._response_cache.get(cache_key)
        
        if cached_item:
            cached_time, cached_result = cached_item
            if time.time() - cached_time < self.config.cache_ttl:
                return cached_result
            else:
                # Remove expired cache entry
                del self._response_cache[cache_key]
        
        return None
    
    def _cache_response(self, query: GraphQLQuery, result: GraphQLResult) -> None:
        """Cache response for query."""
        cache_key = self._generate_cache_key(query)
        self._response_cache[cache_key] = (time.time(), result)
    
    def _generate_cache_key(self, query: GraphQLQuery) -> str:
        """Generate cache key for query."""
        import hashlib
        
        query_str = json.dumps({
            "query": query.query,
            "variables": query.variables,
            "operationName": query.operation_name
        }, sort_keys=True)
        
        return hashlib.sha256(query_str.encode()).hexdigest()
    
    @property
    def schema(self) -> Optional[GraphQLSchema]:
        """Get current schema."""
        return self._schema
    
    def clear_cache(self) -> None:
        """Clear response cache."""
        self._response_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._response_cache),
            "schema_cached": self._schema is not None,
            "schema_cache_age": time.time() - self._schema_cache_time if self._schema_cache_time else None
        }
