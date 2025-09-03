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
from typing import Any, Dict, List, Optional, Tuple, Union, cast
import hashlib
from collections import defaultdict

import aiohttp

from ..auth import AuthManager
from ..utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, with_circuit_breaker
from ..utils.error_handler import EnhancedErrorHandler, RetryConfig, RetryStrategy
from ..utils.metrics import MetricsCollector, record_request_metrics
# Removed unused import that caused unresolved reference
# from ..exceptions import WebFetchError
from .models import (
    GraphQLConfig,
    GraphQLError,
    GraphQLExecutionError,
    GraphQLMutation,
    GraphQLNetworkError,
    GraphQLQuery,
    GraphQLRateLimitError,
    GraphQLResult,
    GraphQLSchema,
    GraphQLSubscription,
    GraphQLTimeoutError,
    GraphQLValidationError,
)
from .validator import GraphQLValidator
from .managers import (
    ManagerFactory,
    GraphQLSessionManager,
    SessionManagerConfig,
    GraphQLSchemaManager,
    SchemaManagerConfig,
    GraphQLCacheManager,
    CacheManagerConfig,
    GraphQLBatchManager,
    BatchManagerConfig,
)

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
        auth_manager: Optional[AuthManager] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize GraphQL client.

        Args:
            config: GraphQL configuration
            auth_manager: Optional authentication manager
            circuit_breaker_config: Optional circuit breaker configuration
        """
        self.config = config
        self.auth_manager = auth_manager

        # Initialize circuit breaker
        self._circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            failure_exceptions=(GraphQLNetworkError,),
        )
        self._circuit_breaker = CircuitBreaker("graphql_client", self._circuit_breaker_config)

        # Initialize retry strategy
        self._retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0,
            jitter=True,
        )
        self._error_handler = EnhancedErrorHandler(self._retry_config)

        # Initialize metrics collection
        self._metrics_collector = MetricsCollector()

        # Initialize manager factory and managers
        self._manager_factory = ManagerFactory()
        self._session_manager: Optional[GraphQLSessionManager] = None
        self._schema_manager: Optional[GraphQLSchemaManager] = None
        self._cache_manager: Optional[GraphQLCacheManager] = None
        self._batch_manager: Optional[GraphQLBatchManager] = None

        # Legacy compatibility - these will be delegated to managers
        self._session: Optional[aiohttp.ClientSession] = None
        self._schema: Optional[GraphQLSchema] = None
        self._schema_cache_time: Optional[float] = None
        self._validator: Optional[GraphQLValidator] = None

        # Legacy cache state - will be moved to cache manager
        self._response_cache: Dict[str, Tuple[float, GraphQLResult, int, int]] = {}
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_size_bytes": 0,
        }
        self._max_cache_size_bytes = 50 * 1024 * 1024  # 50MB default

        # Legacy batch state - will be moved to batch manager
        self._batch_queue: List[GraphQLQuery] = []
        self._batch_task: Optional[asyncio.Task] = None

        # Legacy deduplication state - will be moved to batch manager
        self._pending_queries: Dict[str, asyncio.Future[GraphQLResult]] = {}
        self._deduplication_stats = {
            "total_requests": 0,
            "deduplicated_requests": 0,
            "active_deduplication_keys": 0,
        }

        # Initialize managers
        self._initialize_managers()

    def _initialize_managers(self) -> None:
        """Initialize all GraphQL managers."""
        # Create session manager
        session_config = SessionManagerConfig(
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        self._session_manager = GraphQLSessionManager(
            config=session_config,
            graphql_config=self.config,
            auth_manager=self.auth_manager,
            circuit_breaker_config=self._circuit_breaker_config,
        )

        # Create schema manager
        schema_config = SchemaManagerConfig(
            timeout=self.config.timeout,
            cache_ttl=self.config.schema_cache_ttl,
            validate_queries=self.config.validate_queries,
            auto_introspect=self.config.introspection_enabled,
        )
        self._schema_manager = GraphQLSchemaManager(
            config=schema_config,
            graphql_config=self.config,
            session_manager=self._session_manager,
        )

        # Create cache manager
        cache_config = CacheManagerConfig(
            max_cache_size_bytes=50 * 1024 * 1024,  # 50MB default
            default_ttl=self.config.cache_ttl,
            enable_metrics=True,
        )
        self._cache_manager = GraphQLCacheManager(cache_config)

        # Create batch manager
        batch_config = BatchManagerConfig(
            batch_size=self.config.max_batch_size,
            batch_timeout=0.1,
            enable_batching=self.config.enable_query_batching,
            enable_deduplication=True,
        )
        self._batch_manager = GraphQLBatchManager(
            config=batch_config,
            executor_callback=self._execute_batch_callback,
        )

        # Register managers with factory
        self._manager_factory.register_manager("session", self._session_manager)
        self._manager_factory.register_manager("schema", self._schema_manager, dependencies=["session"])
        self._manager_factory.register_manager("cache", self._cache_manager)
        self._manager_factory.register_manager("batch", self._batch_manager)

        # TODO: Initialize other managers (subscription)
        # This will be done in subsequent tasks

    async def _execute_batch_callback(self, queries: List[GraphQLQuery]) -> List[GraphQLResult]:
        """
        Callback for batch manager to execute batches.

        Args:
            queries: List of queries to execute in batch

        Returns:
            List of results
        """
        return await self.execute_batch(queries)

    async def __aenter__(self) -> "GraphQLClient":
        """Async context manager entry."""
        # Initialize all managers
        await self._manager_factory.initialize_all()

        # Legacy compatibility - create session for backward compatibility
        await self._create_session()
        return self

    async def __aexit__(
        self,
        _exc_type: Optional[type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit."""
        # Reference parameters to silence linters complaining about unused variables
        _ = (_exc_type, _exc_val, _exc_tb)

        # Close all managers
        await self._manager_factory.close_all()

        # Legacy compatibility - close session
        await self._close_session()

    async def _create_session(self) -> None:
        """
        Create HTTP session with optimized connection pooling.

        Legacy method for backward compatibility.
        Session management is now handled by GraphQLSessionManager.
        """
        # Delegate to session manager if available
        if self._session_manager and self._session_manager.is_initialized:
            # Get session from manager to populate legacy _session attribute
            async with self._session_manager.get_session() as session:
                self._session = session
                return

        # Fallback to legacy session creation for compatibility
        if not self._session:
            # Optimized connection pooling configuration
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=30,  # Connections per host
                ttl_dns_cache=300,  # DNS cache TTL (5 minutes)
                use_dns_cache=True,
                keepalive_timeout=30,  # Keep connections alive for 30 seconds
                enable_cleanup_closed=True,  # Clean up closed connections
            )

            timeout = aiohttp.ClientTimeout(
                total=self.config.timeout,
                connect=10.0,  # Connection timeout
                sock_read=30.0,  # Socket read timeout
            )

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": "web-fetch-graphql/1.0"},
                raise_for_status=False,  # Handle status codes manually
            )

    async def _close_session(self) -> None:
        """
        Close HTTP session and cleanup connections.

        Legacy method for backward compatibility.
        Session cleanup is now handled by GraphQLSessionManager.
        """
        # Session manager handles cleanup automatically
        # This is kept for legacy compatibility
        if self._session and not self._session.closed:
            # Gracefully close all connections
            await self._session.close()
            # Wait a bit for connections to close properly
            await asyncio.sleep(0.1)
        self._session = None

    async def execute(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        use_cache: bool = True,
    ) -> GraphQLResult:
        """
        Execute a GraphQL operation with deduplication support.

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
        # Guard for type checker/runtime
        if self._session is None:
            raise GraphQLError("HTTP session is not initialized")

        self._deduplication_stats["total_requests"] += 1

        try:
            # Validate query if enabled
            if self.config.validate_queries:
                try:
                    await self._validate_query(query)
                except GraphQLError as e:
                    # Re-raise validation errors with enhanced context
                    raise GraphQLValidationError(
                        f"Query validation failed: {str(e)}",
                        query=query.query,
                        variables=query.variables,
                        original_error=e,
                    )

            # Check cache for queries (not mutations/subscriptions)
            if (
                use_cache
                and self.config.enable_response_caching
                and isinstance(query, GraphQLQuery)
                and not isinstance(query, (GraphQLMutation, GraphQLSubscription))
            ):
                cached_result = await self._get_cached_response(query)
                if cached_result is not None:
                    return cached_result

            # Use batch manager for query deduplication and batching
            if (self._batch_manager and self._batch_manager.is_initialized and
                isinstance(query, GraphQLQuery) and not isinstance(query, (GraphQLMutation, GraphQLSubscription))):
                # Delegate to batch manager for deduplication and batching
                future = await self._batch_manager.add_query(query)
                return await future
            else:
                # Execute mutations/subscriptions directly (no deduplication/batching)
                return await self._execute_query_with_circuit_breaker(query, use_cache)

        except asyncio.TimeoutError as e:
            raise GraphQLTimeoutError(
                f"GraphQL request timeout: {str(e)}",
                timeout_duration=self.config.timeout,
                query=query.query,
                variables=query.variables,
                endpoint=str(self.config.endpoint),
                original_error=e,
            )
        except aiohttp.ClientError as e:
            raise GraphQLNetworkError(
                f"GraphQL network error: {str(e)}",
                endpoint=str(self.config.endpoint),
                query=query.query,
                variables=query.variables,
                original_error=e,
            )
        except Exception as e:
            if isinstance(e, GraphQLError):
                raise
            raise GraphQLError(
                f"Unexpected GraphQL error: {str(e)}",
                query=query.query,
                variables=query.variables,
                original_error=e,
            )

    async def _execute_query_with_circuit_breaker(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        use_cache: bool = True,
    ) -> GraphQLResult:
        """Execute GraphQL query with circuit breaker protection and retry strategy."""
        async def _protected_execution() -> GraphQLResult:
            return await self._execute_with_retry(query, use_cache)

        return cast(GraphQLResult, await with_circuit_breaker(
            url=str(self.config.endpoint),
            func=_protected_execution,
        ))

    async def _execute_with_retry(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        use_cache: bool = True,
    ) -> GraphQLResult:
        """Execute GraphQL query with retry logic."""
        last_error = None
        attempt = 0

        while attempt <= self._error_handler.default_retry_config.max_retries:
            try:
                return await self._execute_query_internal(query, use_cache)
            except Exception as e:
                last_error = e

                # Categorize the error
                error_info = self._error_handler.categorize_error(
                    exception=e,
                    url=str(self.config.endpoint)
                )

                # Check if we should retry
                if not self._error_handler.should_retry(error_info, attempt):
                    raise e

                # Calculate delay
                delay = self._error_handler.calculate_delay(error_info, attempt)

                # Record error for adaptive strategies
                self._error_handler.record_error(str(self.config.endpoint), error_info)

                # Wait before retry
                if delay > 0:
                    await asyncio.sleep(delay)

                attempt += 1

        # All retries exhausted
        if last_error:
            raise last_error

        # This should never be reached, but just in case
        raise GraphQLError("All retry attempts failed")

    async def _execute_query_internal(
        self,
        query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription],
        use_cache: bool = True,
    ) -> GraphQLResult:
        """Internal method to execute GraphQL operations."""
        # Execute the operation
        start_time = time.time()

        # Prepare request
        request_data = query.to_dict()
        headers = self.config.headers.copy()
        headers["Content-Type"] = "application/json"

        # Add authentication if available
        if self.auth_manager:
            auth_result = await self.auth_manager.authenticate_for_url(
                str(self.config.endpoint)
            )
            if auth_result.success:
                headers.update(auth_result.headers)

        # Make request using session manager
        if self._session_manager and self._session_manager.is_initialized:
            # Use session manager for HTTP requests
            async with self._session_manager.get_session() as session:
                # Apply authentication through session manager
                headers = await self._session_manager.apply_authentication(headers)
                async with session.post(
                    str(self.config.endpoint), json=request_data, headers=headers
                ) as response:
                    response_time = time.time() - start_time
                    response_text = await response.text()
        else:
            # Fallback to legacy session for compatibility
            if self._session is None:
                raise GraphQLError("No session available - client not properly initialized")
            session = self._session  # Now type checker knows it's not None
            async with session.post(
                str(self.config.endpoint), json=request_data, headers=headers
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()

        # Parse response (common for both session manager and legacy paths)
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            raise GraphQLError(f"Invalid JSON response: {response_text}")

        # Create result
        result = GraphQLResult(
            success=response.status == 200 and "errors" not in response_data,
            data=response_data.get("data"),
            errors=response_data.get("errors", []),
            extensions=(
                response_data.get("extensions")
                if self.config.include_extensions
                else None
            ),
            response_time=response_time,
            status_code=response.status,
            headers=dict(response.headers),
            raw_response=response_text,
        )

        # Record metrics for the GraphQL request
        error_message = None
        if result.has_errors:
            error_message = "; ".join(result.error_messages)

        record_request_metrics(
            url=str(self.config.endpoint),
            method="POST",
            status_code=response.status,
            response_time=response_time,
            response_size=len(response_text),
            error=error_message,
        )

        # Handle errors with enhanced categorization
        if result.has_errors and self.config.raise_on_errors:
            error_messages = "; ".join(result.error_messages)

            # Categorize GraphQL errors based on response status
            if response.status == 429:
                retry_after = None
                if "retry-after" in response.headers:
                    try:
                        retry_after = float(response.headers["retry-after"])
                    except ValueError:
                        pass
                raise GraphQLRateLimitError(
                    f"GraphQL rate limit exceeded: {error_messages}",
                    retry_after=retry_after,
                    query=query.query,
                    variables=query.variables,
                    status_code=response.status,
                    response_data=response_data,
                )
            elif response.status >= 500:
                raise GraphQLExecutionError(
                    f"GraphQL server error: {error_messages}",
                    status_code=response.status,
                    response_data=response_data,
                    query=query.query,
                    variables=query.variables,
                )
            else:
                raise GraphQLExecutionError(
                    f"GraphQL execution errors: {error_messages}",
                    status_code=response.status,
                    response_data=response_data,
                    query=query.query,
                    variables=query.variables,
                )

        # Cache successful query results
        if (
            use_cache
            and result.success
            and self.config.enable_response_caching
            and isinstance(query, GraphQLQuery)
            and not isinstance(query, (GraphQLMutation, GraphQLSubscription))
        ):
            await self._cache_response(query, result)

        return result

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
            single_results: List[GraphQLResult] = []
            for query in queries:
                result = await self.execute(query)
                single_results.append(result)
            return single_results

        if not self._session:
            await self._create_session()
        if self._session is None:
            raise GraphQLError("HTTP session is not initialized")

        try:
            # Prepare batch request
            batch_data = [query.to_dict() for query in queries]
            headers = self.config.headers.copy()
            headers["Content-Type"] = "application/json"

            # Add authentication
            if self.auth_manager:
                auth_result = await self.auth_manager.authenticate_for_url(
                    str(self.config.endpoint)
                )
                if auth_result.success:
                    headers.update(auth_result.headers)

            start_time = time.time()

            # Make batch request using session manager
            response = None
            if self._session_manager and self._session_manager.is_initialized:
                # Use session manager for HTTP requests
                async with self._session_manager.get_session() as session:
                    # Apply authentication through session manager
                    headers = await self._session_manager.apply_authentication(headers)
                    async with session.post(
                        str(self.config.endpoint), json=batch_data, headers=headers
                    ) as response:
                        response_time = time.time() - start_time
                        response_text = await response.text()
            else:
                # Fallback to legacy session for compatibility
                session = self._session
                async with session.post(
                    str(self.config.endpoint), json=batch_data, headers=headers
                ) as response:
                    response_time = time.time() - start_time
                    response_text = await response.text()

            # Process response data (common for both paths)
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                raise GraphQLError(f"Invalid JSON response: {response_text}")

            # Parse batch results
            if not isinstance(response_data, list):
                raise GraphQLError("Expected array response for batch request")

            results: List[GraphQLResult] = []
            for item in response_data:
                result = GraphQLResult(
                    success=response.status == 200 and "errors" not in item,
                    data=item.get("data"),
                    errors=item.get("errors", []),
                    extensions=(
                        item.get("extensions")
                        if self.config.include_extensions
                        else None
                    ),
                    response_time=response_time / max(len(response_data), 1),  # Approximate
                    status_code=response.status,
                    headers=dict(response.headers),
                    raw_response=json.dumps(item),
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
        # Delegate to schema manager if available
        if self._schema_manager and self._schema_manager.is_initialized:
            schema = await self._schema_manager.get_schema(force_refresh=force_refresh)
            if schema:
                # Update legacy attributes for compatibility
                self._schema = schema
                self._schema_cache_time = time.time()
                return schema
            else:
                raise GraphQLError("Schema introspection failed")

        # Fallback to legacy introspection for compatibility
        # Check cache
        if (
            not force_refresh
            and self._schema
            and self._schema_cache_time
            and time.time() - self._schema_cache_time < self.config.schema_cache_ttl
        ):
            return self._schema

        if not self.config.introspection_enabled:
            raise GraphQLError("Schema introspection is disabled")

        # Introspection query
        introspection_query = GraphQLQuery(
            query="""
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
            """
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
            mutations=(
                schema_data.get("mutationType", {}).get("fields", [])
                if schema_data.get("mutationType")
                else []
            ),
            subscriptions=(
                schema_data.get("subscriptionType", {}).get("fields", [])
                if schema_data.get("subscriptionType")
                else []
            ),
            directives=schema_data.get("directives", []),
        )

        self._schema_cache_time = time.time()

        # Initialize validator with schema
        if self.config.validate_queries:
            self._validator = GraphQLValidator(self._schema)

        return self._schema

    async def _validate_query(
        self, query: Union[GraphQLQuery, GraphQLMutation, GraphQLSubscription]
    ) -> None:
        """Validate GraphQL query against schema."""
        if not query.validate():
            raise GraphQLError("Invalid query syntax")

        # Delegate to schema manager if available
        if self._schema_manager and self._schema_manager.is_initialized:
            is_valid = await self._schema_manager.validate_query(query)
            if not is_valid:
                raise GraphQLError("Query validation failed")
            return

        # Fallback to legacy validation for compatibility
        if self._validator:
            validation_result = await self._validator.validate(query)
            if not validation_result.is_valid:
                raise GraphQLError(
                    f"Query validation failed: {validation_result.errors}"
                )

    async def _get_cached_response(self, query: GraphQLQuery) -> Optional[GraphQLResult]:
        """Get cached response for query with enhanced cache management."""
        # Delegate to cache manager if available
        if self._cache_manager and self._cache_manager.is_initialized:
            cache_key = self._cache_manager.generate_cache_key(
                query.query, query.variables, query.operation_name
            )
            return await self._cache_manager.get(cache_key)

        # Fallback to legacy caching for compatibility
        cache_key = self._generate_cache_key(query)
        cached_item = self._response_cache.get(cache_key)

        if cached_item:
            cached_time, cached_result, access_count, size_bytes = cached_item
            if time.time() - cached_time < self.config.cache_ttl:
                # Update access count for LRU tracking
                self._response_cache[cache_key] = (
                    cached_time,
                    cached_result,
                    access_count + 1,
                    size_bytes
                )
                self._cache_stats["hits"] += 1
                return cached_result
            else:
                # Remove expired cache entry
                self._evict_cache_entry(cache_key)

        self._cache_stats["misses"] += 1
        return None

    async def _cache_response(self, query: GraphQLQuery, result: GraphQLResult) -> None:
        """Cache response for query with size management."""
        # Delegate to cache manager if available
        if self._cache_manager and self._cache_manager.is_initialized:
            cache_key = self._cache_manager.generate_cache_key(
                query.query, query.variables, query.operation_name
            )
            await self._cache_manager.set(cache_key, result, ttl=self.config.cache_ttl)
            return

        # Fallback to legacy caching for compatibility
        cache_key = self._generate_cache_key(query)

        # Calculate approximate size of the cached result
        result_size = self._estimate_result_size(result)

        # Check if we need to evict entries to make room
        self._ensure_cache_space(result_size)

        # Cache the result with metadata
        self._response_cache[cache_key] = (time.time(), result, 1, result_size)
        self._cache_stats["total_size_bytes"] += result_size

    def _generate_cache_key(self, query: GraphQLQuery) -> str:
        """Generate cache key for query."""
        query_str = json.dumps(
            {
                "query": query.query,
                "variables": query.variables,
                "operationName": query.operation_name,
            },
            sort_keys=True,
        )

        return hashlib.sha256(query_str.encode()).hexdigest()

    def _generate_deduplication_key(self, query: GraphQLQuery) -> str:
        """Generate deduplication key for query (similar to cache key but separate)."""
        # Include endpoint in deduplication key to handle multiple endpoints
        query_str = json.dumps(
            {
                "endpoint": str(self.config.endpoint),
                "query": query.query,
                "variables": query.variables,
                "operationName": query.operation_name,
            },
            sort_keys=True,
        )

        return hashlib.sha256(query_str.encode()).hexdigest()

    @property
    def schema(self) -> Optional[GraphQLSchema]:
        """Get current schema."""
        # Delegate to schema manager if available
        if self._schema_manager and self._schema_manager.is_initialized:
            # Try to get schema from manager (non-blocking)
            if hasattr(self._schema_manager, '_schema'):
                return self._schema_manager._schema

        # Fallback to legacy schema for compatibility
        return self._schema

    def _estimate_result_size(self, result: GraphQLResult) -> int:
        """Estimate the memory size of a GraphQL result."""
        import sys

        # Rough estimation of result size in bytes
        size = sys.getsizeof(result)
        if result.data:
            size += len(str(result.data).encode('utf-8'))
        if result.raw_response:
            size += len(result.raw_response.encode('utf-8'))
        return size

    def _ensure_cache_space(self, needed_size: int) -> None:
        """Ensure there's enough cache space by evicting LRU entries if needed."""
        while (self._cache_stats["total_size_bytes"] + needed_size > self._max_cache_size_bytes
               and self._response_cache):
            # Find least recently used entry (lowest access count, then oldest)
            lru_key = min(
                self._response_cache.keys(),
                key=lambda k: (self._response_cache[k][2], self._response_cache[k][0])
            )
            self._evict_cache_entry(lru_key)

    def _evict_cache_entry(self, cache_key: str) -> None:
        """Evict a single cache entry and update stats."""
        if cache_key in self._response_cache:
            _, _, _, size_bytes = self._response_cache[cache_key]
            del self._response_cache[cache_key]
            self._cache_stats["total_size_bytes"] -= size_bytes
            self._cache_stats["evictions"] += 1

    async def clear_cache(self) -> None:
        """Clear response cache and reset stats."""
        # Delegate to cache manager if available
        if self._cache_manager and self._cache_manager.is_initialized:
            await self._cache_manager.clear()
            return

        # Fallback to legacy cache clearing for compatibility
        self._response_cache.clear()
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_size_bytes": 0,
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache and deduplication statistics."""
        # Delegate to cache manager if available
        if self._cache_manager and self._cache_manager.is_initialized:
            cache_metrics = self._cache_manager.get_metrics()
            # Merge with deduplication stats for compatibility
            dedup_rate = 0.0
            if self._deduplication_stats["total_requests"] > 0:
                dedup_rate = (
                    self._deduplication_stats["deduplicated_requests"]
                    / self._deduplication_stats["total_requests"]
                )

            return {
                **cache_metrics,
                # Add deduplication stats
                "deduplication_rate": dedup_rate,
                "deduplicated_requests": self._deduplication_stats["deduplicated_requests"],
                "total_dedup_requests": self._deduplication_stats["total_requests"],
                "active_deduplication_keys": self._deduplication_stats["active_deduplication_keys"],
                # Schema stats for compatibility
                "schema_cached": self._schema is not None,
                "schema_cache_age": (
                    time.time() - self._schema_cache_time
                    if self._schema_cache_time
                    else None
                ),
            }

        # Fallback to legacy cache stats for compatibility
        hit_rate = 0.0
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        if total_requests > 0:
            hit_rate = self._cache_stats["hits"] / total_requests

        dedup_rate = 0.0
        if self._deduplication_stats["total_requests"] > 0:
            dedup_rate = (
                self._deduplication_stats["deduplicated_requests"]
                / self._deduplication_stats["total_requests"]
            )

        return {
            # Cache statistics
            "cache_size": len(self._response_cache),
            "cache_hit_rate": hit_rate,
            "cache_hits": self._cache_stats["hits"],
            "cache_misses": self._cache_stats["misses"],
            "cache_evictions": self._cache_stats["evictions"],
            "total_size_bytes": self._cache_stats["total_size_bytes"],
            "max_size_bytes": self._max_cache_size_bytes,
            "schema_cached": self._schema is not None,
            "schema_cache_age": (
                time.time() - self._schema_cache_time
                if self._schema_cache_time
                else None
            ),
            # Deduplication statistics
            "deduplication_rate": dedup_rate,
            "total_requests": self._deduplication_stats["total_requests"],
            "deduplicated_requests": self._deduplication_stats["deduplicated_requests"],
            "active_deduplication_keys": self._deduplication_stats["active_deduplication_keys"],
        }

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get detailed deduplication statistics."""
        # Delegate to batch manager if available
        if self._batch_manager and self._batch_manager.is_initialized:
            return self._batch_manager.get_metrics()

        # Fallback to legacy deduplication stats for compatibility
        dedup_rate = 0.0
        if self._deduplication_stats["total_requests"] > 0:
            dedup_rate = (
                self._deduplication_stats["deduplicated_requests"]
                / self._deduplication_stats["total_requests"]
            )

        return {
            "deduplication_rate": dedup_rate,
            "total_requests": self._deduplication_stats["total_requests"],
            "deduplicated_requests": self._deduplication_stats["deduplicated_requests"],
            "active_deduplication_keys": self._deduplication_stats["active_deduplication_keys"],
            "pending_queries": len(self._pending_queries),
        }

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        # Calculate next attempt time based on last failure time and recovery timeout
        next_attempt_time = None
        if self._circuit_breaker._last_failure_time > 0:
            next_attempt_time = self._circuit_breaker._last_failure_time + self._circuit_breaker_config.recovery_timeout

        return {
            "state": self._circuit_breaker.state.name,
            "failure_count": self._circuit_breaker._failure_count,
            "success_count": self._circuit_breaker._success_count,
            "last_failure_time": self._circuit_breaker._last_failure_time,
            "next_attempt_time": next_attempt_time,
            "failure_threshold": self._circuit_breaker_config.failure_threshold,
            "recovery_timeout": self._circuit_breaker_config.recovery_timeout,
        }
